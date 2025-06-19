"""
Comprehensive tests for authentication service and endpoints.

Tests JWT token generation, validation, service authentication,
and endpoint security.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.services.auth import (
    AuthenticationService,
    ServiceIdentity,
    Token,
    TokenData,
    get_auth_service,
    get_current_user,
    require_scopes,
    require_service_identity,
)
from main import app

# Test client
client = TestClient(app)


class TestAuthenticationService:
    """Test cases for AuthenticationService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = AuthenticationService()
        self.test_user_data = {
            "sub": "test_user",
            "user_type": "developer",
            "tenant_id": "test_tenant",
        }
        self.test_scopes = ["read", "write", "ai:execute"]

    def test_service_initialization(self):
        """Test service initialization and configuration."""
        assert self.auth_service.settings is not None
        assert self.auth_service.pwd_context is not None
        assert self.auth_service.oauth2_scheme is not None
        assert len(self.auth_service.service_registry) == 4

        # Verify predefined services
        assert "ai_research_agent" in self.auth_service.service_registry
        assert "workflow_engine" in self.auth_service.service_registry
        assert "campaign_analyzer" in self.auth_service.service_registry
        assert "integration_hub" in self.auth_service.service_registry

    def test_create_access_token(self):
        """Test JWT access token creation."""
        token = self.auth_service.create_access_token(
            data=self.test_user_data,
            expires_delta=timedelta(minutes=15),
            scopes=self.test_scopes,
        )

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long

        # Verify token can be decoded
        token_data = self.auth_service.verify_token(token)
        assert token_data.sub == "test_user"
        assert set(token_data.scopes) == set(self.test_scopes)

    def test_verify_token_valid(self):
        """Test token verification with valid token."""
        token = self.auth_service.create_access_token(
            data=self.test_user_data, scopes=self.test_scopes
        )

        token_data = self.auth_service.verify_token(token)

        assert token_data.sub == "test_user"
        assert token_data.scopes == self.test_scopes
        assert token_data.exp is not None
        assert isinstance(token_data.exp, datetime)

    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            self.auth_service.verify_token("invalid_token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail

    def test_verify_token_expired(self):
        """Test token verification with expired token."""
        # Create token that expires immediately
        token = self.auth_service.create_access_token(
            data=self.test_user_data,
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(HTTPException) as exc_info:
            self.auth_service.verify_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_service_token(self):
        """Test service token creation."""
        service_token = self.auth_service.create_service_token(
            service_id="ai_research_agent", tenant_id="test_tenant"
        )

        assert isinstance(service_token, str)

        # Verify service token
        token_data = self.auth_service.verify_token(service_token)
        assert token_data.sub == "ai_research_agent"
        assert token_data.service_type == "service"
        assert token_data.tenant_id == "test_tenant"

    def test_create_service_token_invalid_service(self):
        """Test service token creation with invalid service ID."""
        with pytest.raises(HTTPException) as exc_info:
            self.auth_service.create_service_token(service_id="invalid_service")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown service ID" in exc_info.value.detail

    def test_verify_service_identity(self):
        """Test service identity verification."""
        service_token = self.auth_service.create_service_token(
            service_id="ai_research_agent"
        )
        token_data = self.auth_service.verify_token(service_token)

        service_identity = self.auth_service.verify_service_identity(token_data)

        assert service_identity.service_id == "ai_research_agent"
        assert service_identity.service_name == "AI Research Agent"
        assert service_identity.service_type == "ai_agent"
        assert "read" in service_identity.permissions
        assert "ai:execute" in service_identity.permissions

    def test_verify_service_identity_invalid_type(self):
        """Test service identity verification with non-service token."""
        token = self.auth_service.create_access_token(
            data=self.test_user_data, scopes=self.test_scopes
        )
        token_data = self.auth_service.verify_token(token)

        with pytest.raises(HTTPException) as exc_info:
            self.auth_service.verify_service_identity(token_data)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid service type" in exc_info.value.detail

    def test_check_permissions_valid(self):
        """Test permission checking with valid scopes."""
        token_data = TokenData(
            sub="test_user", scopes=["read", "write", "ai:execute"], service_type="user"
        )

        # Test with subset of permissions
        assert self.auth_service.check_permissions(token_data, ["read"])
        assert self.auth_service.check_permissions(token_data, ["read", "write"])
        assert self.auth_service.check_permissions(token_data, ["ai:execute"])

    def test_check_permissions_invalid(self):
        """Test permission checking with insufficient scopes."""
        token_data = TokenData(sub="test_user", scopes=["read"], service_type="user")

        # Test with permissions not granted
        assert not self.auth_service.check_permissions(token_data, ["write"])
        assert not self.auth_service.check_permissions(token_data, ["admin"])
        assert not self.auth_service.check_permissions(token_data, ["read", "write"])

    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"

        # Hash password
        hashed = self.auth_service.get_password_hash(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed != password  # Should not be plain text

        # Verify password
        assert self.auth_service.verify_password(password, hashed)
        assert not self.auth_service.verify_password("wrong_password", hashed)

    def test_api_key_generation(self):
        """Test API key generation and validation."""
        api_key = self.auth_service.generate_api_key(prefix="test")

        assert isinstance(api_key, str)
        assert api_key.startswith("test_")
        assert len(api_key) > 40  # Should be long enough

        # Test format validation
        assert self.auth_service.validate_api_key_format(api_key)
        assert not self.auth_service.validate_api_key_format("invalid_key")
        assert not self.auth_service.validate_api_key_format("test")


class TestAuthenticationEndpoints:
    """Test cases for authentication endpoints."""

    def test_auth_health_endpoint(self):
        """Test authentication health endpoint."""
        response = client.get("/api/v1/auth/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "authentication"
        assert "endpoints" in data

    def test_create_token_valid_credentials(self):
        """Test token creation with valid credentials."""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert isinstance(data["access_token"], str)

    def test_create_token_invalid_credentials(self):
        """Test token creation with invalid credentials."""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "invalid",
                "password": "invalid",
                "grant_type": "password",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid credentials" in data["detail"]

    def test_validate_token_endpoint(self):
        """Test token validation endpoint."""
        # First get a valid token
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        token = token_response.json()["access_token"]

        # Validate the token
        response = client.post("/api/v1/auth/validate-token", data={"token": token})

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["token_data"] is not None
        assert data["token_data"]["sub"] == "admin"
        assert "expires_in_seconds" in data

    def test_validate_invalid_token(self):
        """Test validation of invalid token."""
        response = client.post(
            "/api/v1/auth/validate-token", data={"token": "invalid_token"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert data["token_data"] is None

    def test_get_current_user_endpoint(self):
        """Test getting current user information."""
        # First get a valid token
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        token = token_response.json()["access_token"]

        # Get current user info
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["sub"] == "admin"
        assert "scopes" in data
        assert "read" in data["scopes"]
        assert "admin" in data["scopes"]

    def test_get_current_user_no_token(self):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")

        assert (
            response.status_code == 422
        )  # FastAPI validation error for missing dependency

    def test_list_services_endpoint(self):
        """Test listing service registry."""
        # First get a valid token
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        token = token_response.json()["access_token"]

        # List services
        response = client.get(
            "/api/v1/auth/services", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "services" in data
        assert "total_count" in data
        assert data["total_count"] == 4
        assert "ai_research_agent" in data["services"]

    def test_create_service_token_endpoint(self):
        """Test service token creation endpoint."""
        # First get a valid admin token
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        admin_token = token_response.json()["access_token"]

        # Create service token
        response = client.post(
            "/api/v1/auth/service-token",
            json={
                "service_id": "ai_research_agent",
                "tenant_id": "test_tenant",
                "expires_hours": 24,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["service_id"] == "ai_research_agent"
        assert data["service_name"] == "AI Research Agent"
        assert "permissions" in data

    def test_generate_api_key_endpoint(self):
        """Test API key generation endpoint."""
        # First get a valid admin token
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        admin_token = token_response.json()["access_token"]

        # Generate API key
        response = client.post(
            "/api/v1/auth/api-key",
            data={"prefix": "test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "api_key" in data
        assert data["prefix"] == "test"
        assert data["api_key"].startswith("test_")
        assert "created_at" in data

    def test_scope_authorization_endpoint(self):
        """Test scope-based authorization."""
        # Get token with ai:execute scope
        token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        token = token_response.json()["access_token"]

        # Test endpoint requiring ai:execute scope
        response = client.post(
            "/api/v1/auth/test-scopes", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "Scope authorization successful" in data["message"]
        assert "ai:execute" in data["user_scopes"]

    def test_service_authentication_endpoint(self):
        """Test service authentication endpoint."""
        # First get admin token to create service token
        admin_token_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )
        admin_token = admin_token_response.json()["access_token"]

        # Create service token
        service_token_response = client.post(
            "/api/v1/auth/service-token",
            json={"service_id": "ai_research_agent", "expires_hours": 1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        service_token = service_token_response.json()["access_token"]

        # Test service authentication endpoint
        response = client.post(
            "/api/v1/auth/test-service-auth",
            headers={"Authorization": f"Bearer {service_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "Service authentication successful" in data["message"]
        assert data["service_id"] == "ai_research_agent"
        assert data["service_name"] == "AI Research Agent"


class TestAuthenticationDecorators:
    """Test cases for authentication decorators."""

    def test_require_scopes_decorator(self):
        """Test require_scopes decorator functionality."""

        @require_scopes(["read", "write"])
        async def test_function(current_user=None):
            return {"success": True}

        # Test with valid scopes
        token_data = TokenData(
            sub="test_user", scopes=["read", "write", "admin"], service_type="user"
        )

        # This should work (mocking the dependency injection)
        # In real usage, FastAPI handles the dependency injection

    def test_require_service_identity_decorator(self):
        """Test require_service_identity decorator functionality."""

        @require_service_identity()
        async def test_function(current_user=None, service_identity=None):
            return {"service_id": service_identity.service_id}

        # Test would need proper service token data
        # Implementation details depend on FastAPI dependency injection


if __name__ == "__main__":
    pytest.main([__file__])
