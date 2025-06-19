"""
WebSocket endpoints for real-time communication.

Provides WebSocket endpoints for AI workflow updates, notifications,
and real-time communication between backend and frontend.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from app.schemas.websocket import (
    MessageType,
    NotificationMessage,
    WorkflowStatusUpdate,
    create_notification_message,
    create_workflow_message,
)
from app.services.websocket import (
    connection_manager,
    get_websocket_auth,
    handle_websocket_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """
    Main WebSocket endpoint for authenticated real-time communication.

    This endpoint handles:
    - Client authentication via JWT token
    - Connection management and session tracking
    - Message routing and broadcasting
    - Error handling and disconnection management

    Usage:
        ws://localhost:8000/api/v1/ws/your-client-id?token=your-jwt-token
    """
    try:
        # Authenticate the WebSocket connection
        auth_info = await get_websocket_auth(websocket, token)

        # Connect the client with authentication info
        session_id = await connection_manager.connect(
            websocket=websocket,
            client_id=client_id,
            user_id=auth_info["user_id"],
            session_data={
                "tenant_id": auth_info["tenant_id"],
                "scopes": auth_info["scopes"],
                "service_type": auth_info.get("service_type"),
            },
        )

        logger.info(
            f"WebSocket connection established for client {client_id}, session {session_id}"
        )

        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()

                # Parse and handle the message
                message = await handle_websocket_message(websocket, client_id, data)
                if message:
                    await process_client_message(client_id, message, auth_info)

            except WebSocketDisconnect:
                logger.info(f"WebSocket client {client_id} disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop for client {client_id}: {e}")
                await connection_manager.send_error_to_client(
                    client_id=client_id,
                    error_code="WEBSOCKET_ERROR",
                    error_message="An error occurred while processing your request",
                    error_details={"error": str(e)},
                )

    except Exception as e:
        logger.error(f"WebSocket connection error for client {client_id}: {e}")
        # Connection will be closed by the exception handler

    finally:
        # Clean up the connection
        connection_manager.disconnect(client_id)


@router.websocket("/ws/public/{client_id}")
async def public_websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Public WebSocket endpoint for non-authenticated connections.

    This endpoint is useful for:
    - Public status updates
    - System announcements
    - Non-sensitive real-time data

    Usage:
        ws://localhost:8000/api/v1/ws/public/your-client-id
    """
    try:
        # Connect without authentication
        session_id = await connection_manager.connect(
            websocket=websocket,
            client_id=client_id,
            user_id=None,
            session_data={"public": True},
        )

        logger.info(f"Public WebSocket connection established for client {client_id}")

        # Main message loop (limited functionality for public connections)
        while True:
            try:
                data = await websocket.receive_text()
                message = await handle_websocket_message(websocket, client_id, data)

                if message:
                    # Limited message processing for public connections
                    await process_public_message(client_id, message)

            except WebSocketDisconnect:
                logger.info(f"Public WebSocket client {client_id} disconnected")
                break
            except Exception as e:
                logger.error(
                    f"Error in public WebSocket loop for client {client_id}: {e}"
                )
                break

    except Exception as e:
        logger.error(f"Public WebSocket connection error for client {client_id}: {e}")

    finally:
        connection_manager.disconnect(client_id)


# Message processing functions
async def process_client_message(
    client_id: str, message: Dict[str, Any], auth_info: Dict[str, Any]
):
    """
    Process messages from authenticated clients.

    Args:
        client_id: Client identifier
        message: Parsed message data
        auth_info: Authentication information
    """
    message_type = message.get("type")

    if message_type == "ping":
        # Handle ping/pong for connection health
        await connection_manager.send_personal_message(
            '{"type": "pong", "timestamp": "' + str(uuid.uuid4()) + '"}', client_id
        )

    elif message_type == "subscribe_workflow":
        # Subscribe to workflow updates
        workflow_id = message.get("workflow_id")
        if workflow_id:
            # Add client to workflow subscription (implement based on needs)
            logger.info(f"Client {client_id} subscribed to workflow {workflow_id}")

    elif message_type == "unsubscribe_workflow":
        # Unsubscribe from workflow updates
        workflow_id = message.get("workflow_id")
        if workflow_id:
            logger.info(f"Client {client_id} unsubscribed from workflow {workflow_id}")

    elif message_type == "get_status":
        # Send current connection status
        status_data = {
            "type": "status_response",
            "client_id": client_id,
            "connected_clients": connection_manager.get_connection_count(),
            "user_connections": connection_manager.get_user_connection_count(
                auth_info["user_id"]
            ),
            "session_info": connection_manager.get_client_info(client_id),
        }
        await connection_manager.send_personal_message(str(status_data), client_id)

    else:
        logger.warning(f"Unknown message type '{message_type}' from client {client_id}")


async def process_public_message(client_id: str, message: Dict[str, Any]):
    """
    Process messages from public (non-authenticated) clients.

    Args:
        client_id: Client identifier
        message: Parsed message data
    """
    message_type = message.get("type")

    if message_type == "ping":
        # Handle ping/pong for connection health
        await connection_manager.send_personal_message(
            '{"type": "pong", "timestamp": "' + str(uuid.uuid4()) + '"}', client_id
        )
    else:
        # Limited functionality for public connections
        logger.info(f"Public client {client_id} sent message type: {message_type}")


# Utility endpoints for connection management
@router.get("/connections/status")
async def get_connections_status():
    """
    Get WebSocket connections status.

    Returns information about active connections, useful for monitoring.
    """
    return {
        "total_connections": connection_manager.get_connection_count(),
        "active_users": connection_manager.get_active_users(),
        "connection_stats": {
            user_id: connection_manager.get_user_connection_count(user_id)
            for user_id in connection_manager.get_active_users()
        },
    }


# Helper functions for broadcasting messages (used by other services)
async def broadcast_workflow_update(
    workflow_update: WorkflowStatusUpdate,
    target_user_id: Optional[str] = None,
    target_tenant_id: Optional[str] = None,
):
    """
    Broadcast a workflow status update to relevant clients.

    Args:
        workflow_update: Workflow status update data
        target_user_id: Specific user to notify (optional)
        target_tenant_id: Specific tenant to notify (optional)
    """
    message = create_workflow_message(
        client_id="system",
        workflow_update=workflow_update,
        message_type=MessageType.WORKFLOW_PROGRESS,
    )

    message_json = message.model_dump_json()

    if target_user_id:
        await connection_manager.send_message_to_user(message_json, target_user_id)
    elif target_tenant_id:
        await connection_manager.broadcast_to_tenant(message_json, target_tenant_id)
    else:
        await connection_manager.broadcast(message_json)


async def broadcast_notification(
    notification: NotificationMessage,
    target_user_id: Optional[str] = None,
    target_tenant_id: Optional[str] = None,
):
    """
    Broadcast a notification to relevant clients.

    Args:
        notification: Notification data
        target_user_id: Specific user to notify (optional)
        target_tenant_id: Specific tenant to notify (optional)
    """
    message = create_notification_message(client_id="system", notification=notification)

    message_json = message.model_dump_json()

    if target_user_id:
        await connection_manager.send_message_to_user(message_json, target_user_id)
    elif target_tenant_id:
        await connection_manager.broadcast_to_tenant(message_json, target_tenant_id)
    else:
        await connection_manager.broadcast(message_json)
