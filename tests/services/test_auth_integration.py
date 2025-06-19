"""
Test suite for Auth Service Integration

Tests the integration between Google OAuth and the FastAPI auth service.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials

from app.core.config import get_settings
from app.services.auth_client import AuthServiceClient, AuthServiceError


@pytest.fixture
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture
def mock_credentials():
    """Create mock Google credentials."""
    return Credentials(
        token="test_access_token",
        refresh_token="test_refresh_token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        scopes=["https://www.googleapis.com/auth/drive"]
    )


@pytest.fixture
def auth_client():
    """Create AuthServiceClient with mocked HTTP client."""
    client = AuthServiceClient()
    client.client = AsyncMock()
    return client


class TestAuthServiceClient:
    """Test suite for AuthServiceClient."""
    
    @pytest.mark.asyncio
    async def test_get_service_token_success(self, auth_client):
        """Test successful service token generation."""
        # Mock admin token response
        admin_response = Mock()
        admin_response.json.return_value = {"access_token": "admin_token"}
        admin_response.raise_for_status = Mock()
        
        # Mock service token response
        service_response = Mock()
        service_response.json.return_value = {
            "access_token": "service_token",
            "expires_in": 3600
        }
        service_response.raise_for_status = Mock()
        
        auth_client.client.post.side_effect = [admin_response, service_response]
        
        token = await auth_client.get_service_token("ai_research_agent")
        
        assert token == "service_token"
        assert len(auth_client.client.post.call_args_list) == 2
    
    @pytest.mark.asyncio
    async def test_store_google_credentials(self, auth_client, mock_credentials):
        """Test storing Google credentials."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")
        
        # Mock store response
        store_response = Mock()
        store_response.raise_for_status = Mock()
        auth_client.client.post.return_value = store_response
        
        result = await auth_client.store_google_credentials(
            "ai_research_agent",
            mock_credentials
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_retrieve_google_credentials(self, auth_client):
        """Test retrieving Google credentials."""
        # Mock service token
        auth_client.get_service_token = AsyncMock(return_value="service_token")
        
        # Mock retrieve response
        retrieve_response = Mock()
        retrieve_response.status_code = 200
        retrieve_response.json.return_value = {
            "credentials": {
                "access_token": "retrieved_token",
                "refresh_token": "retrieved_refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "retrieved_client_id",
                "client_secret": "retrieved_client_secret",
                "scopes": ["https://www.googleapis.com/auth/drive"]
            }
        }
        retrieve_response.raise_for_status = Mock()
        auth_client.client.get.return_value = retrieve_response
        
        credentials = await auth_client.retrieve_google_credentials("ai_research_agent")
        
        assert credentials is not None
        assert credentials.token == "retrieved_token"
        assert credentials.client_id == "retrieved_client_id"
    
    @pytest.mark.asyncio
    async def test_health_check(self, auth_client):
        """Test auth service health check."""
        health_response = Mock()
        health_response.json.return_value = {"status": "healthy"}
        health_response.raise_for_status = Mock()
        auth_client.client.get.return_value = health_response
        
        health = await auth_client.health_check()
        
        assert health["status"] == "healthy" 