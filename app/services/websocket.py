"""
WebSocket connection manager and service.

Handles WebSocket connections, authentication, and real-time message broadcasting
for AI workflow updates and notifications.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer

from app.schemas.websocket import (
    ErrorMessage,
    MessageType,
    WebSocketMessage,
    create_connection_ack,
    create_error_message,
)
from app.services.auth import AuthenticationService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_sessions: Dict[str, Dict] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of client_ids
        self.auth_service = AuthenticationService()

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        user_id: Optional[str] = None,
        session_data: Optional[Dict] = None,
    ) -> str:
        """
        Accept a WebSocket connection and register the client.

        Args:
            websocket: The WebSocket connection
            client_id: Unique identifier for the client
            user_id: Authenticated user ID (if available)
            session_data: Additional session information

        Returns:
            Session ID for the connection
        """
        await websocket.accept()

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Register connection
        self.active_connections[client_id] = websocket
        self.client_sessions[client_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "session_data": session_data or {},
        }

        # Track user connections
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(client_id)

        logger.info(f"WebSocket client {client_id} connected (user: {user_id})")

        # Send connection acknowledgment
        ack_message = create_connection_ack(client_id, session_id)
        await self.send_personal_message(ack_message.model_dump_json(), client_id)

        return session_id

    def disconnect(self, client_id: str):
        """
        Disconnect a WebSocket client.

        Args:
            client_id: The client identifier to disconnect
        """
        if client_id in self.active_connections:
            # Remove from user connections tracking
            session = self.client_sessions.get(client_id, {})
            user_id = session.get("user_id")
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(client_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Remove connection and session
            del self.active_connections[client_id]
            del self.client_sessions[client_id]

            logger.info(f"WebSocket client {client_id} disconnected (user: {user_id})")

    async def send_personal_message(self, message: str, client_id: str):
        """
        Send a message to a specific client.

        Args:
            message: JSON message string
            client_id: Target client identifier
        """
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(message)

                # Update last activity
                if client_id in self.client_sessions:
                    self.client_sessions[client_id]["last_activity"] = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                self.disconnect(client_id)

    async def send_message_to_user(self, message: str, user_id: str):
        """
        Send a message to all connections for a specific user.

        Args:
            message: JSON message string
            user_id: Target user identifier
        """
        if user_id in self.user_connections:
            client_ids = list(self.user_connections[user_id])
            await asyncio.gather(
                *[
                    self.send_personal_message(message, client_id)
                    for client_id in client_ids
                ],
                return_exceptions=True,
            )

    async def broadcast(
        self, message: str, exclude_clients: Optional[List[str]] = None
    ):
        """
        Broadcast a message to all connected clients.

        Args:
            message: JSON message string
            exclude_clients: List of client IDs to exclude from broadcast
        """
        exclude_clients = exclude_clients or []
        client_ids = [
            client_id
            for client_id in self.active_connections.keys()
            if client_id not in exclude_clients
        ]

        if client_ids:
            await asyncio.gather(
                *[
                    self.send_personal_message(message, client_id)
                    for client_id in client_ids
                ],
                return_exceptions=True,
            )

    async def broadcast_to_tenant(
        self, message: str, tenant_id: str, exclude_clients: Optional[List[str]] = None
    ):
        """
        Broadcast a message to all clients in a specific tenant.

        Args:
            message: JSON message string
            tenant_id: Target tenant identifier
            exclude_clients: List of client IDs to exclude
        """
        exclude_clients = exclude_clients or []
        tenant_clients = [
            client_id
            for client_id, session in self.client_sessions.items()
            if (
                session.get("session_data", {}).get("tenant_id") == tenant_id
                and client_id not in exclude_clients
            )
        ]

        if tenant_clients:
            await asyncio.gather(
                *[
                    self.send_personal_message(message, client_id)
                    for client_id in tenant_clients
                ],
                return_exceptions=True,
            )

    def get_connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self.active_connections)

    def get_user_connection_count(self, user_id: str) -> int:
        """Get the number of connections for a specific user."""
        return len(self.user_connections.get(user_id, set()))

    def get_client_info(self, client_id: str) -> Optional[Dict]:
        """Get information about a specific client connection."""
        return self.client_sessions.get(client_id)

    def get_active_users(self) -> List[str]:
        """Get a list of all users with active connections."""
        return list(self.user_connections.keys())

    async def send_error_to_client(
        self,
        client_id: str,
        error_code: str,
        error_message: str,
        error_details: Optional[Dict] = None,
    ):
        """
        Send an error message to a specific client.

        Args:
            client_id: Target client identifier
            error_code: Error code identifier
            error_message: Human-readable error message
            error_details: Additional error details
        """
        error_msg = create_error_message(
            client_id=client_id,
            error=ErrorMessage(
                error_code=error_code,
                error_message=error_message,
                error_details=error_details,
            ),
        )
        await self.send_personal_message(error_msg.model_dump_json(), client_id)

    async def cleanup_inactive_connections(self, timeout_minutes: int = 30):
        """
        Clean up connections that have been inactive for too long.

        Args:
            timeout_minutes: Inactivity timeout in minutes
        """
        current_time = datetime.utcnow()
        inactive_clients = []

        for client_id, session in self.client_sessions.items():
            last_activity = session.get("last_activity", session.get("connected_at"))
            if last_activity:
                inactive_duration = (current_time - last_activity).total_seconds() / 60
                if inactive_duration > timeout_minutes:
                    inactive_clients.append(client_id)

        for client_id in inactive_clients:
            logger.info(f"Cleaning up inactive WebSocket connection: {client_id}")
            websocket = self.active_connections.get(client_id)
            if websocket:
                try:
                    await websocket.close(
                        code=status.WS_1000_NORMAL_CLOSURE, reason="Inactive"
                    )
                except:
                    pass  # Connection might already be closed
            self.disconnect(client_id)


# Global connection manager instance
connection_manager = ConnectionManager()


async def get_websocket_auth(websocket: WebSocket, token: Optional[str] = None) -> Dict:
    """
    WebSocket authentication dependency.

    Validates JWT token and returns user information.

    Args:
        websocket: WebSocket connection
        token: JWT token (from query parameters)

    Returns:
        Dictionary with user information

    Raises:
        WebSocketException: If authentication fails
    """
    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token required"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )

    try:
        auth_service = AuthenticationService()
        payload = auth_service.verify_token(token)

        return {
            "user_id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "scopes": payload.get("scopes", []),
            "service_type": payload.get("service_type"),
        }

    except Exception as e:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Invalid authentication token: {str(e)}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
        )


# Utility functions for message handling
async def handle_websocket_message(
    websocket: WebSocket, client_id: str, message_data: str
) -> Optional[Dict]:
    """
    Handle incoming WebSocket message.

    Args:
        websocket: WebSocket connection
        client_id: Client identifier
        message_data: Raw message data

    Returns:
        Parsed message dictionary or None if parsing fails
    """
    try:
        message = json.loads(message_data)

        # Update client activity
        if client_id in connection_manager.client_sessions:
            connection_manager.client_sessions[client_id][
                "last_activity"
            ] = datetime.utcnow()

        return message

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from client {client_id}: {e}")
        await connection_manager.send_error_to_client(
            client_id=client_id,
            error_code="INVALID_JSON",
            error_message="Message must be valid JSON",
            error_details={"error": str(e)},
        )
        return None
    except Exception as e:
        logger.error(f"Error processing message from client {client_id}: {e}")
        await connection_manager.send_error_to_client(
            client_id=client_id,
            error_code="MESSAGE_PROCESSING_ERROR",
            error_message="Error processing message",
            error_details={"error": str(e)},
        )
        return None
