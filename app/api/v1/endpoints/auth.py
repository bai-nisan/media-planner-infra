"""
Authentication endpoints for JWT token handling and service authentication.

Provides endpoints for token generation, validation, and service-to-service authentication.
"""

from datetime import timedelta, datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel

from app.services.auth import (
    get_auth_service,
    AuthenticationService,
    Token,
    TokenData,
    ServiceIdentity,
    get_current_user,
    require_scopes,
    require_service_identity
)

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


@router.post("/token", response_model=Token)
async def create_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> Token:
    """
    OAuth2 compatible token endpoint for user authentication.
    
    This endpoint accepts username/password credentials and returns a JWT token.
    Currently configured for development - integrates with your existing user system.
    """
    # For development, we'll accept any credentials
    # In production, this would validate against your user database
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    # Development mode - accept test credentials
    if form_data.username == "admin" and form_data.password == "admin123":
        user_data = {
            "sub": form_data.username,
            "user_type": "admin",
            "tenant_id": "default"
        }
        scopes = ["read", "write", "admin", "ai:execute", "ai:manage"]
    elif form_data.username.startswith("dev"):
        user_data = {
            "sub": form_data.username,
            "user_type": "developer", 
            "tenant_id": "default"
        }
        scopes = ["read", "write", "ai:execute"]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Apply requested scopes (intersection with allowed scopes)
    requested_scopes = form_data.scopes if form_data.scopes else scopes
    final_scopes = list(set(requested_scopes) & set(scopes))
    
    # Create access token
    access_token_expires = timedelta(minutes=auth_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data=user_data,
        expires_delta=access_token_expires,
        scopes=final_scopes
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=" ".join(final_scopes) if final_scopes else None
    )


@router.post("/service-token", response_model=ServiceTokenResponse)
async def create_service_token(
    request: ServiceTokenRequest,
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> ServiceTokenResponse:
    """
    Generate JWT token for service-to-service authentication.
    
    Requires admin permissions to create service tokens.
    """
    # Check if user has admin permissions
    if not auth_service.check_permissions(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to create service tokens"
        )
    
    # Create service token
    expires_delta = timedelta(hours=request.expires_hours)
    service_token = auth_service.create_service_token(
        service_id=request.service_id,
        tenant_id=request.tenant_id,
        expires_delta=expires_delta
    )
    
    # Get service details
    service_identity = auth_service.service_registry[request.service_id]
    
    return ServiceTokenResponse(
        access_token=service_token,
        token_type="bearer",
        expires_in=request.expires_hours * 3600,  # Convert to seconds
        service_id=request.service_id,
        service_name=service_identity.service_name,
        permissions=service_identity.permissions
    )


@router.post("/validate-token", response_model=TokenValidationResponse)
async def validate_token(
    token: str = Form(...),
    auth_service: AuthenticationService = Depends(get_auth_service)
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
            service_identity=service_identity
        )
        
    except HTTPException:
        return TokenValidationResponse(
            valid=False,
            token_data=None,
            expires_in_seconds=None,
            service_identity=None
        )


@router.get("/me", response_model=TokenData)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Get current user/service information from token.
    
    Protected endpoint that returns the decoded token data.
    """
    return current_user


@router.get("/services", response_model=ServiceRegistryResponse)
async def list_service_registry(
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> ServiceRegistryResponse:
    """
    List all registered services for service-to-service authentication.
    
    Requires read permissions.
    """
    if not auth_service.check_permissions(current_user, ["read"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read permissions required"
        )
    
    return ServiceRegistryResponse(
        services=auth_service.service_registry,
        total_count=len(auth_service.service_registry)
    )


@router.post("/api-key", response_model=ApiKeyResponse)
async def generate_api_key(
    prefix: str = Form(default="mp"),
    current_user: TokenData = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> ApiKeyResponse:
    """
    Generate a secure API key for external integrations.
    
    Requires admin permissions.
    """
    if not auth_service.check_permissions(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to generate API keys"
        )
    
    api_key = auth_service.generate_api_key(prefix=prefix)
    
    return ApiKeyResponse(
        api_key=api_key,
        prefix=prefix,
        created_at=datetime.utcnow().isoformat()
    )


@router.post("/test-service-auth")
@require_service_identity()
async def test_service_authentication(
    service_identity: ServiceIdentity,
    current_user: TokenData = Depends(get_current_user)
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
        "token_scopes": current_user.scopes
    }


@router.post("/test-scopes")
@require_scopes(["ai:execute"])
async def test_scope_requirements(
    current_user: TokenData = Depends(get_current_user)
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
        "service_type": current_user.service_type
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
            "services": "/api/v1/auth/services"
        }
    } 