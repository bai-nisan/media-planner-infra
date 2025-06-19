"""
Enhanced Google API Authentication Manager with Auth Service Integration

Provides Google OAuth 2.0 authentication with seamless integration to the FastAPI
auth service for credential storage and management across LangGraph agents.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from app.core.config import Settings
from app.services.auth_client import AuthServiceClient, AuthServiceError
from app.services.google.auth import GoogleAuthManager  # Import base class

logger = logging.getLogger(__name__)


class AuthServiceIntegratedManager(GoogleAuthManager):
    """
    Enhanced Google Auth Manager with auth service integration.

    Extends the base GoogleAuthManager to use the auth service for
    credential storage and retrieval, providing seamless authentication
    for LangGraph agents and multi-tenant environments.
    """

    def __init__(
        self,
        settings: Settings,
        service_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
    ):
        """
        Initialize the enhanced auth manager.

        Args:
            settings: Application settings
            service_id: Service ID for auth service registration
            tenant_id: Tenant ID for multi-tenant environments
            auth_service_url: Custom auth service URL
        """
        super().__init__(settings)

        self.service_id = service_id or "ai_research_agent"
        self.tenant_id = tenant_id
        self.auth_service_url = auth_service_url

        # Initialize auth service client
        self.auth_client = AuthServiceClient(base_url=auth_service_url)

        # Flag to determine credential source priority
        self.prefer_auth_service = True

        logger.info(
            f"Initialized AuthServiceIntegratedManager for service '{self.service_id}'"
        )

    async def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Get valid Google credentials with auth service integration.

        First attempts to retrieve from auth service, then falls back
        to local file storage if unavailable.

        Returns:
            Valid Google credentials or None if unavailable
        """
        try:
            # Try auth service first
            if self.prefer_auth_service:
                credentials = await self._get_credentials_from_service()
                if credentials:
                    logger.info("Using credentials from auth service")
                    return credentials
                else:
                    logger.info("No credentials found in auth service, trying local")

            # Fallback to local storage
            credentials = self.load_credentials()
            if credentials:
                logger.info("Using credentials from local storage")

                # Optionally sync to auth service
                if self.prefer_auth_service:
                    await self._sync_credentials_to_service(credentials)

                return credentials

            logger.warning("No valid credentials found in any source")
            return None

        except Exception as e:
            logger.error(f"Error retrieving credentials: {e}")
            # Try fallback to local storage
            return self.load_credentials()

    async def exchange_code_for_credentials(
        self, authorization_code: str, redirect_uri: str, store_in_service: bool = True
    ) -> Credentials:
        """
        Exchange authorization code for credentials and store in auth service.

        Args:
            authorization_code: OAuth authorization code
            redirect_uri: Redirect URI used in OAuth flow
            store_in_service: Whether to store credentials in auth service

        Returns:
            Google credentials object
        """
        # Use parent implementation to get credentials
        credentials = super().exchange_code_for_credentials(
            authorization_code, redirect_uri
        )

        # Store in auth service if enabled
        if store_in_service and credentials:
            try:
                await self._store_credentials_in_service(credentials)
                logger.info("Credentials stored in auth service")
            except Exception as e:
                logger.warning(f"Failed to store credentials in auth service: {e}")

        return credentials

    async def refresh_credentials(self, force: bool = False) -> Optional[Credentials]:
        """
        Refresh expired credentials and update storage.

        Args:
            force: Force refresh even if credentials appear valid

        Returns:
            Refreshed credentials or None if refresh failed
        """
        try:
            # Get current credentials
            credentials = await self.get_valid_credentials()
            if not credentials:
                logger.warning("No credentials available to refresh")
                return None

            # Check if refresh is needed
            if not force and not credentials.expired:
                logger.debug("Credentials not expired, skipping refresh")
                return credentials

            # Refresh credentials
            if credentials.refresh_token:
                logger.info("Refreshing expired credentials")
                credentials.refresh(Request())

                # Update both local and service storage
                self._save_credentials(credentials)
                await self._store_credentials_in_service(credentials)

                logger.info("Credentials refreshed and updated")
                return credentials
            else:
                logger.warning("No refresh token available")
                return None

        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            return None

    async def revoke_credentials(self) -> bool:
        """
        Revoke credentials from both local and auth service storage.

        Returns:
            True if credentials were revoked successfully
        """
        success = True

        # Revoke from auth service
        try:
            async with self.auth_client as client:
                await client.revoke_credentials(self.service_id, self.tenant_id)
            logger.info("Credentials revoked from auth service")
        except Exception as e:
            logger.warning(f"Failed to revoke from auth service: {e}")
            success = False

        # Revoke locally
        try:
            local_success = super().revoke_credentials()
            if not local_success:
                success = False
        except Exception as e:
            logger.warning(f"Failed to revoke local credentials: {e}")
            success = False

        return success

    async def get_credential_status(self) -> Dict[str, Any]:
        """
        Get comprehensive credential status from all sources.

        Returns:
            Status information including auth service and local storage
        """
        status = {
            "service_id": self.service_id,
            "tenant_id": self.tenant_id,
            "sources": {},
        }

        # Check auth service
        try:
            async with self.auth_client as client:
                service_status = await client.validate_credentials(
                    self.service_id, self.tenant_id
                )
            status["sources"]["auth_service"] = {
                "available": True,
                "has_credentials": service_status.has_credentials,
                "credentials_valid": service_status.credentials_valid,
                "expires_at": service_status.expires_at,
                "scopes": service_status.scopes,
            }
        except Exception as e:
            status["sources"]["auth_service"] = {"available": False, "error": str(e)}

        # Check local storage
        try:
            local_credentials = super().get_valid_credentials()
            status["sources"]["local_storage"] = {
                "available": True,
                "has_credentials": local_credentials is not None,
                "credentials_valid": (
                    not local_credentials.expired
                    if local_credentials and local_credentials.expiry
                    else True
                ),
                "scopes": local_credentials.scopes if local_credentials else [],
            }
        except Exception as e:
            status["sources"]["local_storage"] = {"available": False, "error": str(e)}

        # Overall status
        has_any_credentials = any(
            source.get("has_credentials", False)
            for source in status["sources"].values()
            if source.get("available", False)
        )

        has_valid_credentials = any(
            source.get("credentials_valid", False)
            for source in status["sources"].values()
            if source.get("available", False) and source.get("has_credentials", False)
        )

        status["overall"] = {
            "has_credentials": has_any_credentials,
            "credentials_valid": has_valid_credentials,
            "primary_source": (
                "auth_service" if self.prefer_auth_service else "local_storage"
            ),
        }

        return status

    async def _get_credentials_from_service(self) -> Optional[Credentials]:
        """
        Retrieve credentials from the auth service.

        Returns:
            Google credentials or None if not found
        """
        try:
            async with self.auth_client as client:
                return await client.retrieve_google_credentials(
                    self.service_id, self.tenant_id, auto_refresh=True
                )
        except AuthServiceError as e:
            logger.warning(f"Auth service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving from service: {e}")
            return None

    async def _store_credentials_in_service(self, credentials: Credentials) -> bool:
        """
        Store credentials in the auth service.

        Args:
            credentials: Google credentials to store

        Returns:
            True if stored successfully
        """
        try:
            async with self.auth_client as client:
                return await client.store_google_credentials(
                    self.service_id, credentials, self.tenant_id
                )
        except AuthServiceError as e:
            logger.warning(f"Auth service error storing credentials: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing credentials: {e}")
            return False

    async def _sync_credentials_to_service(self, credentials: Credentials) -> bool:
        """
        Sync local credentials to the auth service.

        Args:
            credentials: Local credentials to sync

        Returns:
            True if synced successfully
        """
        try:
            logger.info("Syncing local credentials to auth service")
            return await self._store_credentials_in_service(credentials)
        except Exception as e:
            logger.warning(f"Failed to sync credentials to service: {e}")
            return False


class AgentAuthManagerFactory:
    """
    Factory for creating auth managers for different agent types.

    Provides convenient creation of auth managers with appropriate
    service IDs and configurations for different LangGraph agents.
    """

    @staticmethod
    def create_workspace_agent_auth(
        settings: Settings,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
    ) -> AuthServiceIntegratedManager:
        """Create auth manager for workspace agent."""
        return AuthServiceIntegratedManager(
            settings=settings,
            service_id="ai_research_agent",
            tenant_id=tenant_id,
            auth_service_url=auth_service_url,
        )

    @staticmethod
    def create_planning_agent_auth(
        settings: Settings,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
    ) -> AuthServiceIntegratedManager:
        """Create auth manager for planning agent."""
        return AuthServiceIntegratedManager(
            settings=settings,
            service_id="campaign_analyzer",
            tenant_id=tenant_id,
            auth_service_url=auth_service_url,
        )

    @staticmethod
    def create_insights_agent_auth(
        settings: Settings,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
    ) -> AuthServiceIntegratedManager:
        """Create auth manager for insights agent."""
        return AuthServiceIntegratedManager(
            settings=settings,
            service_id="campaign_analyzer",
            tenant_id=tenant_id,
            auth_service_url=auth_service_url,
        )

    @staticmethod
    def create_integration_auth(
        settings: Settings,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
    ) -> AuthServiceIntegratedManager:
        """Create auth manager for integration hub."""
        return AuthServiceIntegratedManager(
            settings=settings,
            service_id="integration_hub",
            tenant_id=tenant_id,
            auth_service_url=auth_service_url,
        )


# Context manager for auto-cleanup
class ManagedGoogleAuth:
    """
    Context manager for Google authentication with automatic cleanup.

    Provides a convenient way to use Google authentication with
    automatic resource cleanup and error handling.
    """

    def __init__(
        self, auth_manager: AuthServiceIntegratedManager, auto_refresh: bool = True
    ):
        """
        Initialize managed auth context.

        Args:
            auth_manager: Auth manager instance
            auto_refresh: Automatically refresh expired credentials
        """
        self.auth_manager = auth_manager
        self.auto_refresh = auto_refresh
        self.credentials: Optional[Credentials] = None

    async def __aenter__(self) -> Optional[Credentials]:
        """Enter context and get credentials."""
        try:
            self.credentials = await self.auth_manager.get_valid_credentials()

            if self.auto_refresh and self.credentials and self.credentials.expired:
                self.credentials = await self.auth_manager.refresh_credentials()

            return self.credentials
        except Exception as e:
            logger.error(f"Failed to get credentials in context: {e}")
            return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context with cleanup."""
        # Cleanup is handled by the auth manager
        pass


# Helper functions for common use cases
async def get_workspace_credentials(
    settings: Settings, tenant_id: Optional[str] = None
) -> Optional[Credentials]:
    """
    Helper function to get credentials for workspace agent.

    Args:
        settings: Application settings
        tenant_id: Optional tenant ID

    Returns:
        Google credentials or None
    """
    auth_manager = AgentAuthManagerFactory.create_workspace_agent_auth(
        settings, tenant_id
    )

    async with ManagedGoogleAuth(auth_manager) as credentials:
        return credentials


async def get_planning_credentials(
    settings: Settings, tenant_id: Optional[str] = None
) -> Optional[Credentials]:
    """
    Helper function to get credentials for planning agent.

    Args:
        settings: Application settings
        tenant_id: Optional tenant ID

    Returns:
        Google credentials or None
    """
    auth_manager = AgentAuthManagerFactory.create_planning_agent_auth(
        settings, tenant_id
    )

    async with ManagedGoogleAuth(auth_manager) as credentials:
        return credentials
