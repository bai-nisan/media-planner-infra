"""
Test suite for Auth Service Integration

Tests the integration between Google OAuth and the FastAPI auth service,
including credential storage, retrieval, and management across agents.
"""

import json
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from google.oauth2.credentials import Credentials

from app.core.config import get_settings
from app.services.auth_client import (
    AuthServiceClient,
    AuthServiceError,
    GoogleCredentialsData,
    ServiceCredentialStatus,
    get_agent_credentials,
)
from app.services.google.auth_enhanced import (
    AgentAuthManagerFactory,
    AuthServiceIntegratedManager,
    ManagedGoogleAuth,
    get_planning_credentials,
    get_workspace_credentials,
)


@pytest.fixture
def settings():
    """Get test settings."""
    settings = get_settings()
    return settings


@pytest.fixture
def mock_credentials():
    """Create mock Google credentials."""
    return Credentials(
        token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        id_token="eyJ0test",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )


@pytest.fixture
def mock_httpx_client():
    """Create mock httpx client."""
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    return mock_client


@pytest.fixture
def auth_client(mock_httpx_client):
    """Create AuthServiceClient with mocked HTTP client."""
    client = AuthServiceClient()
    client.client = mock_httpx_client
    return client


class TestAuthServiceClient:
    """Test suite for AuthServiceClient."""

    @pytest.mark.asyncio
    async def test_get_service_token_success(self, auth_client, mock_httpx_client):
        """Test successful service token generation."""
        # Mock admin token response
        admin_response = Mock()
        admin_response.json.return_value = {"access_token": "admin_token"}
        admin_response.raise_for_status = Mock()

        # Mock service token response
        service_response = Mock()
        service_response.json.return_value = {
            "access_token": "service_token",
            "expires_in": 3600,
            "service_id": "ai_research_agent",
        }
        service_response.raise_for_status = Mock()

        mock_httpx_client.post.side_effect = [admin_response, service_response]

        token = await auth_client.get_service_token("ai_research_agent")

        assert token == "service_token"
        assert len(mock_httpx_client.post.call_args_list) == 2

        # Check admin token call
        admin_call = mock_httpx_client.post.call_args_list[0]
        assert admin_call[0][0] == "/api/v1/auth/token"

        # Check service token call
        service_call = mock_httpx_client.post.call_args_list[1]
        assert service_call[0][0] == "/api/v1/auth/service-token"

    @pytest.mark.asyncio
    async def test_get_service_token_cached(self, auth_client, mock_httpx_client):
        """Test service token caching."""
        # Set up cache
        auth_client._service_token_cache["ai_research_agent:default"] = {
            "token": "cached_token",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }

        token = await auth_client.get_service_token("ai_research_agent")

        assert token == "cached_token"
        # Should not make HTTP calls for cached token
        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_google_credentials(
        self, auth_client, mock_httpx_client, mock_credentials
    ):
        """Test storing Google credentials."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")

        # Mock store response
        store_response = Mock()
        store_response.json.return_value = {
            "message": "Credentials stored successfully"
        }
        store_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = store_response

        result = await auth_client.store_google_credentials(
            "ai_research_agent", mock_credentials
        )

        assert result is True

        # Verify the call
        store_call = mock_httpx_client.post.call_args
        assert store_call[0][0] == "/api/v1/auth/credentials/google/ai_research_agent"

        # Check credentials data
        request_data = store_call[1]["json"]
        assert request_data["credentials"]["access_token"] == "ya29.test_access_token"
        assert request_data["credentials"]["client_id"] == "test_client_id"

    @pytest.mark.asyncio
    async def test_retrieve_google_credentials(self, auth_client, mock_httpx_client):
        """Test retrieving Google credentials."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")

        # Mock retrieve response
        retrieve_response = Mock()
        retrieve_response.status_code = 200
        retrieve_response.json.return_value = {
            "credentials": {
                "access_token": "ya29.retrieved_token",
                "refresh_token": "1//retrieved_refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "retrieved_client_id",
                "client_secret": "retrieved_client_secret",
                "scopes": ["https://www.googleapis.com/auth/drive"],
            }
        }
        retrieve_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = retrieve_response

        credentials = await auth_client.retrieve_google_credentials("ai_research_agent")

        assert credentials is not None
        assert credentials.token == "ya29.retrieved_token"
        assert credentials.client_id == "retrieved_client_id"
        assert "https://www.googleapis.com/auth/drive" in credentials.scopes

    @pytest.mark.asyncio
    async def test_retrieve_google_credentials_not_found(
        self, auth_client, mock_httpx_client
    ):
        """Test retrieving non-existent credentials."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")

        # Mock 404 response
        not_found_response = Mock()
        not_found_response.status_code = 404
        mock_httpx_client.get.return_value = not_found_response

        credentials = await auth_client.retrieve_google_credentials(
            "nonexistent_service"
        )

        assert credentials is None

    @pytest.mark.asyncio
    async def test_validate_credentials(self, auth_client):
        """Test credential validation."""
        # Mock credential retrieval
        mock_credentials = Mock()
        mock_credentials.expired = False
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        mock_credentials.scopes = ["https://www.googleapis.com/auth/drive"]

        auth_client.retrieve_google_credentials = AsyncMock(
            return_value=mock_credentials
        )

        status = await auth_client.validate_credentials("ai_research_agent")

        assert status.service_id == "ai_research_agent"
        assert status.has_credentials is True
        assert status.credentials_valid is True
        assert status.scopes == ["https://www.googleapis.com/auth/drive"]

    @pytest.mark.asyncio
    async def test_revoke_credentials(self, auth_client, mock_httpx_client):
        """Test credential revocation."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")

        # Mock revoke response
        revoke_response = Mock()
        revoke_response.raise_for_status = Mock()
        mock_httpx_client.delete.return_value = revoke_response

        result = await auth_client.revoke_credentials("ai_research_agent")

        assert result is True

        # Verify delete call
        delete_call = mock_httpx_client.delete.call_args
        assert delete_call[0][0] == "/api/v1/auth/credentials/google/ai_research_agent"

    @pytest.mark.asyncio
    async def test_health_check(self, auth_client, mock_httpx_client):
        """Test auth service health check."""
        # Mock health response
        health_response = Mock()
        health_response.json.return_value = {"status": "healthy"}
        health_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = health_response

        health = await auth_client.health_check()

        assert health["status"] == "healthy"
        mock_httpx_client.get.assert_called_once_with("/api/v1/auth/health")


class TestAuthServiceIntegratedManager:
    """Test suite for AuthServiceIntegratedManager."""

    @pytest.fixture
    def auth_manager(self, settings):
        """Create AuthServiceIntegratedManager for testing."""
        return AuthServiceIntegratedManager(
            settings=settings, service_id="ai_research_agent", tenant_id="test_tenant"
        )

    @pytest.mark.asyncio
    async def test_get_valid_credentials_from_service(
        self, auth_manager, mock_credentials
    ):
        """Test getting credentials from auth service."""
        # Mock auth service client
        auth_manager.auth_client = AsyncMock()
        auth_manager.auth_client.__aenter__ = AsyncMock(
            return_value=auth_manager.auth_client
        )
        auth_manager.auth_client.__aexit__ = AsyncMock(return_value=None)
        auth_manager.auth_client.retrieve_google_credentials = AsyncMock(
            return_value=mock_credentials
        )

        credentials = await auth_manager.get_valid_credentials()

        assert credentials == mock_credentials
        auth_manager.auth_client.retrieve_google_credentials.assert_called_once_with(
            "ai_research_agent", "test_tenant", auto_refresh=True
        )

    @pytest.mark.asyncio
    async def test_get_valid_credentials_fallback_to_local(
        self, auth_manager, mock_credentials
    ):
        """Test fallback to local credentials when service unavailable."""
        # Mock auth service to return None
        auth_manager._get_credentials_from_service = AsyncMock(return_value=None)

        # Mock local credentials
        auth_manager.load_credentials = Mock(return_value=mock_credentials)
        auth_manager._sync_credentials_to_service = AsyncMock(return_value=True)

        credentials = await auth_manager.get_valid_credentials()

        assert credentials == mock_credentials
        auth_manager._sync_credentials_to_service.assert_called_once_with(
            mock_credentials
        )

    @pytest.mark.asyncio
    async def test_exchange_code_for_credentials(self, auth_manager, mock_credentials):
        """Test OAuth code exchange with auth service storage."""
        # Mock parent implementation
        with patch.object(
            auth_manager.__class__.__bases__[0],
            "exchange_code_for_credentials",
            return_value=mock_credentials,
        ):
            auth_manager._store_credentials_in_service = AsyncMock(return_value=True)

            result = await auth_manager.exchange_code_for_credentials(
                "test_code", "http://localhost:8000/callback"
            )

            assert result == mock_credentials
            auth_manager._store_credentials_in_service.assert_called_once_with(
                mock_credentials
            )

    @pytest.mark.asyncio
    async def test_refresh_credentials(self, auth_manager, mock_credentials):
        """Test credential refresh and storage update."""
        # Mock expired credentials
        expired_credentials = Mock()
        # Mock underlying expiry mechanism to make expired property return True
        expired_credentials._expiry = datetime.utcnow() - timedelta(seconds=1)
        expired_credentials.expired = (
            True  # This will now work because we're using a Mock
        )
        expired_credentials.refresh_token = "refresh_token"
        expired_credentials.refresh = Mock()

        auth_manager.get_valid_credentials = AsyncMock(return_value=expired_credentials)
        auth_manager._save_credentials = Mock()
        auth_manager._store_credentials_in_service = AsyncMock(return_value=True)

        result = await auth_manager.refresh_credentials()

        assert result == expired_credentials
        expired_credentials.refresh.assert_called_once()
        auth_manager._save_credentials.assert_called_once_with(expired_credentials)
        auth_manager._store_credentials_in_service.assert_called_once_with(
            expired_credentials
        )

    @pytest.mark.asyncio
    async def test_revoke_credentials(self, auth_manager):
        """Test credential revocation from both sources."""
        # Mock auth service revocation
        auth_manager.auth_client = AsyncMock()
        auth_manager.auth_client.__aenter__ = AsyncMock(
            return_value=auth_manager.auth_client
        )
        auth_manager.auth_client.__aexit__ = AsyncMock(return_value=None)
        auth_manager.auth_client.revoke_credentials = AsyncMock(return_value=True)

        # Mock local revocation
        with patch.object(
            auth_manager.__class__.__bases__[0], "revoke_credentials", return_value=True
        ):
            result = await auth_manager.revoke_credentials()

            assert result is True
            auth_manager.auth_client.revoke_credentials.assert_called_once_with(
                "ai_research_agent", "test_tenant"
            )

    @pytest.mark.asyncio
    async def test_get_credential_status(self, auth_manager, mock_credentials):
        """Test comprehensive credential status check."""
        # Mock auth service status
        service_status = Mock()
        service_status.has_credentials = True
        service_status.credentials_valid = True
        service_status.expires_at = datetime.utcnow() + timedelta(hours=1)
        service_status.scopes = ["https://www.googleapis.com/auth/drive"]

        auth_manager.auth_client = AsyncMock()
        auth_manager.auth_client.__aenter__ = AsyncMock(
            return_value=auth_manager.auth_client
        )
        auth_manager.auth_client.__aexit__ = AsyncMock(return_value=None)
        auth_manager.auth_client.validate_credentials = AsyncMock(
            return_value=service_status
        )

        # Mock local status
        with (
            patch.object(
                auth_manager.__class__.__bases__[0],
                "get_valid_credentials",
                return_value=mock_credentials,
            ),
            patch.object(
                type(mock_credentials),
                "expired",
                new_callable=lambda: property(lambda self: False),
            ),
        ):
            mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)

            status = await auth_manager.get_credential_status()

            assert status["service_id"] == "ai_research_agent"
            assert status["tenant_id"] == "test_tenant"
            assert status["sources"]["auth_service"]["has_credentials"] is True
            assert status["sources"]["local_storage"]["has_credentials"] is True
            assert status["overall"]["has_credentials"] is True
            assert status["overall"]["credentials_valid"] is True


class TestAgentAuthManagerFactory:
    """Test suite for AgentAuthManagerFactory."""

    def test_create_workspace_agent_auth(self, settings):
        """Test workspace agent auth manager creation."""
        auth_manager = AgentAuthManagerFactory.create_workspace_agent_auth(settings)

        assert isinstance(auth_manager, AuthServiceIntegratedManager)
        assert auth_manager.service_id == "ai_research_agent"

    def test_create_planning_agent_auth(self, settings):
        """Test planning agent auth manager creation."""
        auth_manager = AgentAuthManagerFactory.create_planning_agent_auth(settings)

        assert isinstance(auth_manager, AuthServiceIntegratedManager)
        assert auth_manager.service_id == "campaign_analyzer"

    def test_create_insights_agent_auth(self, settings):
        """Test insights agent auth manager creation."""
        auth_manager = AgentAuthManagerFactory.create_insights_agent_auth(settings)

        assert isinstance(auth_manager, AuthServiceIntegratedManager)
        assert auth_manager.service_id == "campaign_analyzer"

    def test_create_integration_auth(self, settings):
        """Test integration hub auth manager creation."""
        auth_manager = AgentAuthManagerFactory.create_integration_auth(settings)

        assert isinstance(auth_manager, AuthServiceIntegratedManager)
        assert auth_manager.service_id == "integration_hub"


class TestManagedGoogleAuth:
    """Test suite for ManagedGoogleAuth context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self, settings, mock_credentials):
        """Test successful context manager usage."""
        auth_manager = Mock()
        auth_manager.get_valid_credentials = AsyncMock(return_value=mock_credentials)

        async with ManagedGoogleAuth(auth_manager) as credentials:
            assert credentials == mock_credentials

        auth_manager.get_valid_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_refresh(self, settings, mock_credentials):
        """Test context manager with auto-refresh."""
        # Mock expired credentials by patching the expired property
        with patch.object(
            type(mock_credentials),
            "expired",
            new_callable=lambda: property(lambda self: True),
        ):
            auth_manager = Mock()
            auth_manager.get_valid_credentials = AsyncMock(
                return_value=mock_credentials
            )
            auth_manager.refresh_credentials = AsyncMock(return_value=mock_credentials)

            async with ManagedGoogleAuth(
                auth_manager, auto_refresh=True
            ) as credentials:
                assert credentials == mock_credentials

            auth_manager.refresh_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_error_handling(self, settings):
        """Test context manager error handling."""
        auth_manager = Mock()
        auth_manager.get_valid_credentials = AsyncMock(
            side_effect=Exception("Test error")
        )

        async with ManagedGoogleAuth(auth_manager) as credentials:
            assert credentials is None


class TestHelperFunctions:
    """Test suite for helper functions."""

    @pytest.mark.asyncio
    async def test_get_agent_credentials(self):
        """Test helper function for getting agent credentials."""
        mock_credentials = Mock()

        with patch("app.services.auth_client.AuthServiceClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.retrieve_google_credentials = AsyncMock(
                return_value=mock_credentials
            )
            mock_client_class.return_value = mock_client

            credentials = await get_agent_credentials("workspace", "test_tenant")

            assert credentials == mock_credentials
            mock_client.retrieve_google_credentials.assert_called_once_with(
                "ai_research_agent", "test_tenant"
            )

    @pytest.mark.asyncio
    async def test_get_workspace_credentials(self, settings, mock_credentials):
        """Test workspace credentials helper."""
        with patch(
            "app.services.google.auth_enhanced.AgentAuthManagerFactory.create_workspace_agent_auth"
        ) as mock_factory:
            mock_auth_manager = Mock()
            mock_auth_manager.get_valid_credentials = AsyncMock(
                return_value=mock_credentials
            )
            mock_factory.return_value = mock_auth_manager

            credentials = await get_workspace_credentials(settings, "test_tenant")

            assert credentials == mock_credentials
            mock_factory.assert_called_once_with(settings, "test_tenant")

    @pytest.mark.asyncio
    async def test_get_planning_credentials(self, settings, mock_credentials):
        """Test planning credentials helper."""
        with patch(
            "app.services.google.auth_enhanced.AgentAuthManagerFactory.create_planning_agent_auth"
        ) as mock_factory:
            mock_auth_manager = Mock()
            mock_auth_manager.get_valid_credentials = AsyncMock(
                return_value=mock_credentials
            )
            mock_factory.return_value = mock_auth_manager

            credentials = await get_planning_credentials(settings, "test_tenant")

            assert credentials == mock_credentials
            mock_factory.assert_called_once_with(settings, "test_tenant")


class TestIntegrationScenarios:
    """Integration test scenarios."""

    @pytest.mark.asyncio
    async def test_full_credential_lifecycle(self, settings, mock_credentials):
        """Test complete credential lifecycle with auth service."""
        # Create integrated auth manager
        auth_manager = AuthServiceIntegratedManager(
            settings=settings, service_id="ai_research_agent"
        )

        # Mock auth service interactions
        auth_manager.auth_client = AsyncMock()
        auth_manager.auth_client.__aenter__ = AsyncMock(
            return_value=auth_manager.auth_client
        )
        auth_manager.auth_client.__aexit__ = AsyncMock(return_value=None)

        # Test storing credentials
        auth_manager.auth_client.store_google_credentials = AsyncMock(return_value=True)

        store_result = await auth_manager._store_credentials_in_service(
            mock_credentials
        )
        assert store_result is True

        # Test retrieving credentials
        auth_manager.auth_client.retrieve_google_credentials = AsyncMock(
            return_value=mock_credentials
        )

        retrieved = await auth_manager._get_credentials_from_service()
        assert retrieved == mock_credentials

        # Test credential status
        status_mock = Mock()
        status_mock.has_credentials = True
        status_mock.credentials_valid = True
        auth_manager.auth_client.validate_credentials = AsyncMock(
            return_value=status_mock
        )

        status = await auth_manager.get_credential_status()
        assert status["overall"]["has_credentials"] is True

        # Test revocation
        auth_manager.auth_client.revoke_credentials = AsyncMock(return_value=True)
        with patch.object(
            auth_manager.__class__.__bases__[0], "revoke_credentials", return_value=True
        ):
            revoke_result = await auth_manager.revoke_credentials()
            assert revoke_result is True
