"""
Authentication endpoints for JWT tokens, service tokens, and Google credential management.

Provides secure authentication for users and services, plus credential storage
for Google API integrations used by LangGraph agents.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

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

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class ServiceTokenRequest(BaseModel):
    """Request model for service token generation."""

    service_id: str
    tenant_id: Optional[str] = None
    expires_hours: Optional[int] = 24


class ServiceTokenResponse(BaseModel):
    """Response model for service token generation."""

    access_token: str
    token_type: str
    expires_in: int
    service_id: str
    service_name: str
    permissions: List[str]


class TokenValidationResponse(BaseModel):
    """Response model for token validation."""

    valid: bool
    token_data: Optional[TokenData] = None
    expires_in_seconds: Optional[int] = None
    service_identity: Optional[ServiceIdentity] = None


class ApiKeyResponse(BaseModel):
    """Response model for API key generation."""

    api_key: str
    prefix: str
    created_at: str


class ServiceRegistryResponse(BaseModel):
    """Response model for service registry listing."""

    services: Dict[str, ServiceIdentity]
    total_count: int


# Google Credentials Models
class GoogleCredentialsRequest(BaseModel):
    """Request model for storing Google credentials."""

    tenant_id: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    # Supabase provider token fields
    provider_token: Optional[str] = None
    provider_refresh_token: Optional[str] = None
    user_email: Optional[str] = None


class GoogleCredentialsResponse(BaseModel):
    """Response model for Google credentials retrieval."""

    service_id: str
    tenant_id: Optional[str] = None
    credentials: Dict[str, Any]
    stored_at: datetime
    expires_at: Optional[datetime] = None


class CredentialStatusResponse(BaseModel):
    """Response model for credential status."""

    service_id: str
    tenant_id: Optional[str] = None
    has_credentials: bool
    credentials_valid: bool
    expires_at: Optional[datetime] = None
    scopes: List[str] = []
    last_refreshed: Optional[datetime] = None


@router.post("/token", response_model=Token)
async def create_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> Token:
    """
    OAuth2 compatible token endpoint for user authentication.

    Returns JWT access token for API authentication.
    """
    # In a real application, verify username/password against database
    # For development, use simple hardcoded check
    if form_data.username == "admin" and form_data.password == "admin123":
        token_data = {
            "sub": form_data.username,
            "service_type": "user",
            "tenant_id": "default",
        }

        # Include requested scopes
        scopes = form_data.scopes if form_data.scopes else ["read", "write"]

        access_token = auth_service.create_access_token(data=token_data, scopes=scopes)

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/service-token", response_model=ServiceTokenResponse)
async def create_service_token(
    request: ServiceTokenRequest,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> ServiceTokenResponse:
    """
    Generate JWT token for service-to-service authentication.

    Requires admin permissions to create service tokens.
    """
    # Check if user has admin permissions
    if not auth_service.check_permissions(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to create service tokens",
        )

    # Create service token
    expires_delta = timedelta(hours=request.expires_hours)
    service_token = auth_service.create_service_token(
        service_id=request.service_id,
        tenant_id=request.tenant_id,
        expires_delta=expires_delta,
    )

    # Get service details
    service_identity = auth_service.service_registry[request.service_id]

    return ServiceTokenResponse(
        access_token=service_token,
        token_type="bearer",
        expires_in=request.expires_hours * 3600,  # Convert to seconds
        service_id=request.service_id,
        service_name=service_identity.service_name,
        permissions=service_identity.permissions,
    )


@router.post("/validate-token", response_model=TokenValidationResponse)
async def validate_token(
    token: str = Form(...),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> TokenValidationResponse:
    """
    Validate a JWT token and return token information.

    Public endpoint for token validation - useful for service integrations.
    """
    try:
        token_data = auth_service.verify_token(token)

        # Calculate remaining time
        expires_in_seconds = None
        if token_data.exp:
            remaining = token_data.exp - datetime.utcnow()
            expires_in_seconds = max(0, int(remaining.total_seconds()))

        # Check if it's a service token
        service_identity = None
        if token_data.service_type == "service":
            try:
                service_identity = auth_service.verify_service_identity(token_data)
            except HTTPException:
                pass  # Invalid service identity

        return TokenValidationResponse(
            valid=True,
            token_data=token_data,
            expires_in_seconds=expires_in_seconds,
            service_identity=service_identity,
        )

    except HTTPException:
        return TokenValidationResponse(
            valid=False, token_data=None, expires_in_seconds=None, service_identity=None
        )


# Google Credentials Endpoints
@router.post("/credentials/google/{service_id}", response_model=Dict[str, str])
@require_scopes(["ai:execute", "external:write"])
async def store_google_credentials(
    service_id: str,
    request: GoogleCredentialsRequest,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> Dict[str, str]:
    """
    Store Google OAuth credentials for a service.

    Requires ai:execute and external:write permissions.
    Credentials are encrypted and stored securely.
    """
    try:
        # Validate service exists
        if service_id not in auth_service.service_registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found in registry",
            )

        # Store credentials securely using Supabase Vault
        from app.services.credential_storage import (
            GoogleOAuthCredentials,
            get_credential_storage,
        )

        credential_storage = get_credential_storage()

        # Handle both traditional credentials and Supabase provider tokens
        if request.provider_token:
            # Supabase provider token format
            credentials = GoogleOAuthCredentials(
                access_token=request.provider_token,
                refresh_token=request.provider_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id="",  # Will be filled from settings
                client_secret="",  # Will be filled from settings
                scopes=[
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets",
                ],
                user_email=request.user_email,
            )
        else:
            # Traditional credentials format
            cred_data = request.credentials or {}
            credentials = GoogleOAuthCredentials(
                access_token=cred_data.get("access_token", ""),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
                client_id=cred_data.get("client_id", ""),
                client_secret=cred_data.get("client_secret", ""),
                scopes=cred_data.get("scopes", []),
            )

        # Store in Supabase Vault
        success = await credential_storage.store_google_credentials(
            service_id=service_id,
            tenant_id=request.tenant_id or "default",
            credentials=credentials,
            stored_by=current_user.sub,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store credentials securely",
            )

        return {
            "message": "Credentials stored successfully",
            "service_id": service_id,
            "tenant_id": request.tenant_id or "default",
        }

    except Exception as e:
        logger.error(f"Failed to store credentials for {service_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credentials",
        )


@router.get(
    "/credentials/google/{service_id}", response_model=GoogleCredentialsResponse
)
@require_scopes(["ai:execute", "external:read"])
async def retrieve_google_credentials(
    service_id: str,
    tenant_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> GoogleCredentialsResponse:
    """
    Retrieve Google OAuth credentials for a service.

    Requires ai:execute and external:read permissions.
    Returns decrypted credentials for API usage.
    """
    try:
        # Validate service exists
        if service_id not in auth_service.service_registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found in registry",
            )

        # Retrieve credentials from Supabase Vault
        from app.services.credential_storage import get_credential_storage

        credential_storage = get_credential_storage()

        stored_credentials = await credential_storage.retrieve_google_credentials(
            service_id=service_id, tenant_id=tenant_id or "default"
        )

        if not stored_credentials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No credentials found for service {service_id}",
            )

        credentials = stored_credentials.to_dict()

        return GoogleCredentialsResponse(
            service_id=service_id,
            tenant_id=tenant_id,
            credentials=credentials,
            stored_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve credentials for {service_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credentials",
        )


@router.get(
    "/credentials/google/{service_id}/status", response_model=CredentialStatusResponse
)
@require_scopes(["ai:execute"])
async def check_credential_status(
    service_id: str,
    tenant_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> CredentialStatusResponse:
    """
    Check the status of stored Google credentials.

    Requires ai:execute permissions.
    Returns credential validity and expiration info without exposing tokens.
    """
    try:
        # Validate service exists
        if service_id not in auth_service.service_registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found in registry",
            )

        # Check credential status using Supabase Vault
        from app.services.credential_storage import get_credential_storage

        credential_storage = get_credential_storage()

        status_info = await credential_storage.check_credential_status(
            service_id=service_id, tenant_id=tenant_id or "default"
        )

        return CredentialStatusResponse(
            service_id=service_id,
            tenant_id=tenant_id,
            has_credentials=status_info["has_credentials"],
            credentials_valid=status_info["credentials_valid"],
            expires_at=status_info["expires_at"],
            scopes=status_info["scopes"],
            last_refreshed=status_info.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check credential status for {service_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check credential status",
        )


@router.delete("/credentials/google/{service_id}", response_model=Dict[str, str])
@require_scopes(["ai:execute", "external:write"])
async def revoke_google_credentials(
    service_id: str,
    tenant_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> Dict[str, str]:
    """
    Revoke and delete Google OAuth credentials for a service.

    Requires ai:execute and external:write permissions.
    Permanently removes stored credentials.
    """
    try:
        # Validate service exists
        if service_id not in auth_service.service_registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found in registry",
            )

        # Revoke credentials using Supabase Vault
        from app.services.credential_storage import get_credential_storage

        credential_storage = get_credential_storage()

        success = await credential_storage.revoke_credentials(
            service_id=service_id, tenant_id=tenant_id or "default"
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke credentials",
            )

        return {
            "message": "Credentials revoked successfully",
            "service_id": service_id,
            "tenant_id": tenant_id or "default",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke credentials for {service_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke credentials",
        )


@router.get("/credentials/google", response_model=List[Dict[str, Any]])
@require_scopes(["ai:execute"])
async def list_google_credentials(
    tenant_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> List[Dict[str, Any]]:
    """
    List all Google OAuth credentials for a tenant.

    Requires ai:execute permissions.
    Returns credential metadata without sensitive data.
    """
    try:
        from app.services.credential_storage import get_credential_storage

        credential_storage = get_credential_storage()

        credentials = await credential_storage.list_credentials(
            tenant_id=tenant_id or "default"
        )

        # Filter for Google OAuth credentials only
        google_credentials = [
            cred for cred in credentials if cred["credential_type"] == "google_oauth"
        ]

        return google_credentials

    except Exception as e:
        logger.error(f"Failed to list credentials: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list credentials",
        )


@router.post("/credentials/google/{service_id}/refresh", response_model=Dict[str, str])
@require_scopes(["ai:execute", "external:write"])
async def refresh_google_credentials(
    service_id: str,
    request: GoogleCredentialsRequest,
    tenant_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> Dict[str, str]:
    """
    Refresh Google OAuth credentials with new tokens.

    Requires ai:execute and external:write permissions.
    Updates existing credentials with new access/refresh tokens.
    """
    try:
        # Validate service exists
        if service_id not in auth_service.service_registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found in registry",
            )

        from app.services.credential_storage import (
            GoogleOAuthCredentials,
            get_credential_storage,
        )

        credential_storage = get_credential_storage()

        # Handle both traditional credentials and Supabase provider tokens
        if request.provider_token:
            # Supabase provider token format
            new_credentials = GoogleOAuthCredentials(
                access_token=request.provider_token,
                refresh_token=request.provider_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id="",  # Will be preserved from existing
                client_secret="",  # Will be preserved from existing
                scopes=[
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets",
                ],
                user_email=request.user_email,
                expires_at=datetime.utcnow() + timedelta(hours=1),  # Default 1 hour
            )
        else:
            # Traditional credentials format
            cred_data = request.credentials or {}
            expires_at = None
            if cred_data.get("expires_in"):
                expires_at = datetime.utcnow() + timedelta(
                    seconds=int(cred_data["expires_in"])
                )

            new_credentials = GoogleOAuthCredentials(
                access_token=cred_data.get("access_token", ""),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
                client_id=cred_data.get("client_id", ""),
                client_secret=cred_data.get("client_secret", ""),
                scopes=cred_data.get("scopes", []),
                expires_at=expires_at,
            )

        # Refresh credentials in Supabase Vault
        success = await credential_storage.refresh_google_credentials(
            service_id=service_id,
            tenant_id=tenant_id or "default",
            new_credentials=new_credentials,
            updated_by=current_user.sub,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to refresh credentials",
            )

        return {
            "message": "Credentials refreshed successfully",
            "service_id": service_id,
            "tenant_id": tenant_id or "default",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh credentials for {service_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh credentials",
        )


@router.get("/me", response_model=TokenData)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    """
    Get current user/service information from token.

    Protected endpoint that returns the decoded token data.
    """
    return current_user


@router.get("/services", response_model=ServiceRegistryResponse)
async def list_service_registry(
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> ServiceRegistryResponse:
    """
    List all registered services for service-to-service authentication.

    Requires read permissions.
    """
    if not auth_service.check_permissions(current_user, ["read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Read permissions required"
        )

    return ServiceRegistryResponse(
        services=auth_service.service_registry,
        total_count=len(auth_service.service_registry),
    )


@router.post("/api-key", response_model=ApiKeyResponse)
async def generate_api_key(
    prefix: str = Form(default="mp"),
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> ApiKeyResponse:
    """
    Generate a secure API key for external integrations.

    Requires admin permissions.
    """
    if not auth_service.check_permissions(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to generate API keys",
        )

    api_key = auth_service.generate_api_key(prefix=prefix)

    return ApiKeyResponse(
        api_key=api_key, prefix=prefix, created_at=datetime.utcnow().isoformat()
    )


@router.post("/test-service-auth")
@require_service_identity()
async def test_service_authentication(
    service_identity: ServiceIdentity,
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Test endpoint for service-to-service authentication.

    This endpoint requires a valid service token and demonstrates
    the service identity verification process.
    """
    return {
        "message": "Service authentication successful",
        "service_id": service_identity.service_id,
        "service_name": service_identity.service_name,
        "service_type": service_identity.service_type,
        "permissions": service_identity.permissions,
        "tenant_id": service_identity.tenant_id,
        "token_subject": current_user.sub,
        "token_scopes": current_user.scopes,
    }


@router.post("/test-scopes")
@require_scopes(["ai:execute"])
async def test_scope_requirements(
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Test endpoint for scope-based authorization.

    This endpoint requires 'ai:execute' scope to demonstrate
    permission-based access control.
    """
    return {
        "message": "Scope authorization successful",
        "required_scope": "ai:execute",
        "user_scopes": current_user.scopes,
        "user_id": current_user.sub,
        "service_type": current_user.service_type,
    }


@router.get("/health")
async def auth_health_check() -> Dict[str, Any]:
    """
    Authentication service health check.

    Public endpoint to verify the authentication service is operational.
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "token": "/api/v1/auth/token",
            "service_token": "/api/v1/auth/service-token",
            "validate": "/api/v1/auth/validate-token",
            "me": "/api/v1/auth/me",
            "services": "/api/v1/auth/services",
            "google_credentials": {
                "store": "/api/v1/auth/credentials/google/{service_id}",
                "retrieve": "/api/v1/auth/credentials/google/{service_id}",
                "status": "/api/v1/auth/credentials/google/{service_id}/status",
                "refresh": "/api/v1/auth/credentials/google/{service_id}/refresh",
                "revoke": "/api/v1/auth/credentials/google/{service_id}",
                "list": "/api/v1/auth/credentials/google",
            },
        },
    }
