"""
Auth Service Client for Google API Credential Management

Provides integration with the FastAPI auth service endpoints to retrieve
and manage Google OAuth credentials for LangGraph agents and Google API clients.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Union
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from google.oauth2.credentials import Credentials

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GoogleCredentialsData(BaseModel):
    """Pydantic model for Google OAuth credentials data."""
    access_token: str
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: str
    client_secret: str
    scopes: List[str] = []
    expiry: Optional[datetime] = None


class ServiceCredentialStatus(BaseModel):
    """Status information for service credentials."""
    service_id: str
    has_credentials: bool
    credentials_valid: bool
    expires_at: Optional[datetime] = None
    scopes: List[str] = []
    last_refreshed: Optional[datetime] = None
    error_message: Optional[str] = None


class AuthServiceError(Exception):
    """Custom exception for auth service related errors."""
    pass


class AuthServiceClient:
    """
    Client for interfacing with FastAPI auth service endpoints.
    
    Manages Google OAuth credentials through the auth service,
    providing credential retrieval, validation, and refresh functionality
    for LangGraph agents and Google API integrations.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Auth Service Client.
        
        Args:
            base_url: Base URL of the auth service API (defaults to settings)
            api_key: API key for auth service authentication
        """
        self.settings = get_settings()
        self.base_url = base_url or "http://localhost:8000"
        self.api_key = api_key
        
        # Create HTTP client with authentication headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0
        )
        
        # Cache for service tokens
        self._service_token_cache: Dict[str, Dict[str, Any]] = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    async def get_service_token(
        self, 
        service_id: str, 
        tenant_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> str:
        """
        Get a service token for API authentication.
        
        Args:
            service_id: ID of the service (e.g., 'ai_research_agent')
            tenant_id: Optional tenant ID for multi-tenant environments
            force_refresh: Force token refresh even if cached token is valid
            
        Returns:
            Service authentication token
            
        Raises:
            AuthServiceError: If token generation fails
        """
        cache_key = f"{service_id}:{tenant_id or 'default'}"
        
        # Check cache if not forcing refresh
        if not force_refresh and cache_key in self._service_token_cache:
            cached = self._service_token_cache[cache_key]
            if datetime.utcnow() < cached["expires_at"]:
                logger.debug(f"Using cached service token for {service_id}")
                return cached["token"]
        
        try:
            # First get user token for admin operations
            user_token = await self._get_admin_token()
            
            # Request service token
            response = await self.client.post(
                "/api/v1/auth/service-token",
                json={
                    "service_id": service_id,
                    "tenant_id": tenant_id,
                    "expires_hours": 24
                },
                headers={"Authorization": f"Bearer {user_token}"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 24 * 3600)
            
            # Cache the token
            self._service_token_cache[cache_key] = {
                "token": token,
                "expires_at": datetime.utcnow() + timedelta(seconds=expires_in - 300)  # 5 min buffer
            }
            
            logger.info(f"Generated new service token for {service_id}")
            return token
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get service token for {service_id}: {e.response.text}")
            raise AuthServiceError(f"Service token generation failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error getting service token: {e}")
            raise AuthServiceError(f"Service token error: {str(e)}")
    
    async def store_google_credentials(
        self, 
        service_id: str,
        credentials: Credentials,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Store Google OAuth credentials in the auth service.
        
        Args:
            service_id: Service ID to associate credentials with
            credentials: Google OAuth credentials object
            tenant_id: Optional tenant ID
            
        Returns:
            True if stored successfully
            
        Raises:
            AuthServiceError: If storage fails
        """
        try:
            service_token = await self.get_service_token(service_id, tenant_id)
            
            # Convert Google credentials to storable format
            creds_data = {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "id_token": getattr(credentials, 'id_token', None),
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes or [],
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            # Store credentials via auth service
            response = await self.client.post(
                f"/api/v1/auth/credentials/google/{service_id}",
                json={
                    "tenant_id": tenant_id,
                    "credentials": creds_data
                },
                headers={"Authorization": f"Bearer {service_token}"}
            )
            response.raise_for_status()
            
            logger.info(f"Stored Google credentials for service {service_id}")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to store credentials for {service_id}: {e.response.text}")
            raise AuthServiceError(f"Credential storage failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error storing credentials: {e}")
            raise AuthServiceError(f"Credential storage error: {str(e)}")
    
    async def retrieve_google_credentials(
        self, 
        service_id: str,
        tenant_id: Optional[str] = None,
        auto_refresh: bool = True
    ) -> Optional[Credentials]:
        """
        Retrieve Google OAuth credentials for a service.
        
        Args:
            service_id: Service ID to retrieve credentials for
            tenant_id: Optional tenant ID
            auto_refresh: Automatically refresh expired credentials
            
        Returns:
            Google credentials object or None if not found
            
        Raises:
            AuthServiceError: If retrieval fails
        """
        try:
            service_token = await self.get_service_token(service_id, tenant_id)
            
            response = await self.client.get(
                f"/api/v1/auth/credentials/google/{service_id}",
                params={"tenant_id": tenant_id} if tenant_id else {},
                headers={"Authorization": f"Bearer {service_token}"}
            )
            
            if response.status_code == 404:
                logger.info(f"No credentials found for service {service_id}")
                return None
                
            response.raise_for_status()
            creds_data = response.json()["credentials"]
            
            # Convert to Google credentials object
            credentials = Credentials(
                token=creds_data["access_token"],
                refresh_token=creds_data.get("refresh_token"),
                id_token=creds_data.get("id_token"),
                token_uri=creds_data["token_uri"],
                client_id=creds_data["client_id"],
                client_secret=creds_data["client_secret"],
                scopes=creds_data.get("scopes", [])
            )
            
            # Set expiry if available
            if creds_data.get("expiry"):
                credentials.expiry = datetime.fromisoformat(creds_data["expiry"])
            
            # Auto-refresh if needed and enabled
            if auto_refresh and credentials.expired and credentials.refresh_token:
                logger.info(f"Auto-refreshing expired credentials for {service_id}")
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                
                # Store refreshed credentials
                await self.store_google_credentials(service_id, credentials, tenant_id)
            
            logger.info(f"Retrieved Google credentials for service {service_id}")
            return credentials
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                logger.error(f"Failed to retrieve credentials for {service_id}: {e.response.text}")
                raise AuthServiceError(f"Credential retrieval failed: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving credentials: {e}")
            raise AuthServiceError(f"Credential retrieval error: {str(e)}")
    
    async def validate_credentials(
        self, 
        service_id: str,
        tenant_id: Optional[str] = None
    ) -> ServiceCredentialStatus:
        """
        Validate the status of stored credentials for a service.
        
        Args:
            service_id: Service ID to validate
            tenant_id: Optional tenant ID
            
        Returns:
            ServiceCredentialStatus with validation results
        """
        try:
            credentials = await self.retrieve_google_credentials(
                service_id, 
                tenant_id, 
                auto_refresh=False
            )
            
            if not credentials:
                return ServiceCredentialStatus(
                    service_id=service_id,
                    has_credentials=False,
                    credentials_valid=False
                )
            
            # Check if credentials are valid
            is_valid = not credentials.expired if credentials.expiry else True
            
            return ServiceCredentialStatus(
                service_id=service_id,
                has_credentials=True,
                credentials_valid=is_valid,
                expires_at=credentials.expiry,
                scopes=credentials.scopes or [],
                last_refreshed=datetime.utcnow() if is_valid else None
            )
            
        except Exception as e:
            logger.error(f"Error validating credentials for {service_id}: {e}")
            return ServiceCredentialStatus(
                service_id=service_id,
                has_credentials=False,
                credentials_valid=False,
                error_message=str(e)
            )
    
    async def revoke_credentials(
        self, 
        service_id: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Revoke and delete stored credentials for a service.
        
        Args:
            service_id: Service ID to revoke credentials for
            tenant_id: Optional tenant ID
            
        Returns:
            True if revoked successfully
            
        Raises:
            AuthServiceError: If revocation fails
        """
        try:
            service_token = await self.get_service_token(service_id, tenant_id)
            
            response = await self.client.delete(
                f"/api/v1/auth/credentials/google/{service_id}",
                params={"tenant_id": tenant_id} if tenant_id else {},
                headers={"Authorization": f"Bearer {service_token}"}
            )
            response.raise_for_status()
            
            logger.info(f"Revoked Google credentials for service {service_id}")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to revoke credentials for {service_id}: {e.response.text}")
            raise AuthServiceError(f"Credential revocation failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error revoking credentials: {e}")
            raise AuthServiceError(f"Credential revocation error: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the auth service.
        
        Returns:
            Health status information
        """
        try:
            response = await self.client.get("/api/v1/auth/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Auth service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _get_admin_token(self) -> str:
        """
        Get an admin token for service operations.
        
        This is a temporary implementation - in production, this should
        use proper service account credentials or admin user authentication.
        
        Returns:
            Admin authentication token
        """
        try:
            # Use development admin credentials
            response = await self.client.post(
                "/api/v1/auth/token",
                data={
                    "username": "admin",
                    "password": "admin123",
                    "grant_type": "password"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            return response.json()["access_token"]
            
        except Exception as e:
            logger.error(f"Failed to get admin token: {e}")
            raise AuthServiceError(f"Admin authentication failed: {str(e)}")


# Factory function for dependency injection
async def get_auth_service_client() -> AuthServiceClient:
    """
    Factory function to create AuthServiceClient instance.
    
    Used with FastAPI dependency injection.
    """
    return AuthServiceClient()


# Helper function for agent authentication
async def get_agent_credentials(
    agent_type: str,
    tenant_id: Optional[str] = None
) -> Optional[Credentials]:
    """
    Helper function to get Google credentials for an agent.
    
    Args:
        agent_type: Type of agent ('workspace', 'planning', 'insights')
        tenant_id: Optional tenant ID
        
    Returns:
        Google credentials or None if not available
    """
    service_id_map = {
        "workspace": "ai_research_agent",
        "planning": "campaign_analyzer", 
        "insights": "campaign_analyzer"
    }
    
    service_id = service_id_map.get(agent_type, "ai_research_agent")
    
    async with AuthServiceClient() as client:
        return await client.retrieve_google_credentials(service_id, tenant_id) 