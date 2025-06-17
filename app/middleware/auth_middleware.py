"""
Authentication middleware for automatic JWT token processing and validation.

Provides middleware for extracting and validating JWT tokens from requests,
adding user context to requests, and handling authentication errors.
"""

import logging
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.auth import get_auth_service, TokenData

logger = logging.getLogger(__name__)


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic JWT token processing.
    
    Extracts JWT tokens from Authorization headers, validates them,
    and adds user context to requests for downstream processing.
    """
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        """
        Initialize JWT authentication middleware.
        
        Args:
            app: FastAPI application instance
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.auth_service = get_auth_service()
        
        # Default excluded paths (public endpoints)
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/health",
            "/api/v1/health",
            "/api/v1/auth/health",
            "/api/v1/auth/token",
            "/api/v1/auth/validate-token",
            "/api/v1/database/health"
        ]
        
        logger.info(f"JWT Auth Middleware initialized with {len(self.exclude_paths)} excluded paths")
    
    def is_excluded_path(self, path: str) -> bool:
        """
        Check if a path should be excluded from authentication.
        
        Args:
            path: Request path
            
        Returns:
            True if path should be excluded
        """
        # Exact match
        if path in self.exclude_paths:
            return True
        
        # Pattern matching for dynamic paths
        for excluded_path in self.exclude_paths:
            if excluded_path.endswith("*") and path.startswith(excluded_path[:-1]):
                return True
        
        return False
    
    def extract_token_from_header(self, authorization: str) -> Optional[str]:
        """
        Extract JWT token from Authorization header.
        
        Args:
            authorization: Authorization header value
            
        Returns:
            JWT token string or None
        """
        try:
            scheme, token = get_authorization_scheme_param(authorization)
            if scheme.lower() != "bearer":
                return None
            return token
        except Exception:
            return None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with JWT authentication.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with authentication context
        """
        # Check if path should be excluded from authentication
        if self.is_excluded_path(request.url.path):
            logger.debug(f"Skipping auth for excluded path: {request.url.path}")
            return await call_next(request)
        
        # Extract token from Authorization header
        authorization: str = request.headers.get("Authorization")
        token = None
        token_data = None
        
        if authorization:
            token = self.extract_token_from_header(authorization)
            
            if token:
                try:
                    # Validate token
                    token_data = self.auth_service.verify_token(token)
                    
                    # Add authentication context to request state
                    request.state.token = token
                    request.state.token_data = token_data
                    request.state.user = token_data
                    request.state.authenticated = True
                    
                    # Add tenant context if available
                    if token_data.tenant_id:
                        request.state.tenant_id = token_data.tenant_id
                    
                    logger.debug(f"Authenticated request for user: {token_data.sub}")
                    
                except HTTPException as e:
                    # Invalid token
                    logger.warning(f"Invalid token for path {request.url.path}: {e.detail}")
                    return JSONResponse(
                        status_code=e.status_code,
                        content={
                            "detail": e.detail,
                            "error": "authentication_failed",
                            "path": str(request.url.path)
                        }
                    )
                except Exception as e:
                    # Unexpected error during token validation
                    logger.error(f"Token validation error: {str(e)}")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "detail": "Authentication service error",
                            "error": "internal_error"
                        }
                    )
        
        # No token provided for protected endpoint
        if not token_data:
            logger.warning(f"No valid token provided for protected path: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authentication required",
                    "error": "missing_token",
                    "path": str(request.url.path)
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Continue with authenticated request
        try:
            response = await call_next(request)
            
            # Add authentication info to response headers (optional)
            if token_data:
                response.headers["X-User-ID"] = token_data.sub
                if token_data.tenant_id:
                    response.headers["X-Tenant-ID"] = token_data.tenant_id
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing authenticated request: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": "processing_error"
                }
            )


class OptionalJWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Optional JWT authentication middleware.
    
    Similar to JWTAuthenticationMiddleware but doesn't require authentication
    for all endpoints. Adds user context when token is provided but allows
    requests without tokens to proceed.
    """
    
    def __init__(self, app):
        """Initialize optional JWT authentication middleware."""
        super().__init__(app)
        self.auth_service = get_auth_service()
        logger.info("Optional JWT Auth Middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with optional JWT authentication.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with optional authentication context
        """
        # Initialize request state
        request.state.token = None
        request.state.token_data = None
        request.state.user = None
        request.state.authenticated = False
        request.state.tenant_id = None
        
        # Extract token from Authorization header
        authorization: str = request.headers.get("Authorization")
        
        if authorization:
            token = None
            try:
                scheme, token = get_authorization_scheme_param(authorization)
                if scheme.lower() == "bearer" and token:
                    # Validate token
                    token_data = self.auth_service.verify_token(token)
                    
                    # Add authentication context to request state
                    request.state.token = token
                    request.state.token_data = token_data
                    request.state.user = token_data
                    request.state.authenticated = True
                    
                    # Add tenant context if available
                    if token_data.tenant_id:
                        request.state.tenant_id = token_data.tenant_id
                    
                    logger.debug(f"Optional auth: authenticated user {token_data.sub}")
                
            except HTTPException:
                # Invalid token - log but don't block request
                logger.debug(f"Optional auth: invalid token provided for {request.url.path}")
            except Exception as e:
                # Unexpected error - log but don't block request
                logger.warning(f"Optional auth error: {str(e)}")
        
        # Continue with request (authenticated or not)
        response = await call_next(request)
        
        # Add authentication info to response headers if authenticated
        if request.state.authenticated and request.state.token_data:
            response.headers["X-User-ID"] = request.state.token_data.sub
            if request.state.token_data.tenant_id:
                response.headers["X-Tenant-ID"] = request.state.token_data.tenant_id
        
        return response


def get_current_user_from_request(request: Request) -> Optional[TokenData]:
    """
    Get current user from request state (set by middleware).
    
    Args:
        request: FastAPI request object
        
    Returns:
        TokenData if user is authenticated, None otherwise
    """
    return getattr(request.state, "token_data", None)


def require_authentication(request: Request) -> TokenData:
    """
    Require authentication from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TokenData for authenticated user
        
    Raises:
        HTTPException: If user is not authenticated
    """
    token_data = get_current_user_from_request(request)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return token_data 