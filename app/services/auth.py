"""
Authentication service module for JWT token handling and service security.

Provides JWT token generation, validation, and service-to-service authentication
for AI workflow components and external integrations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from functools import wraps
import secrets

from fastapi import HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# Pydantic models for authentication
class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    scope: Optional[str] = None


class TokenData(BaseModel):
    """Token payload data model."""
    sub: Optional[str] = None  # Subject (username or service ID)
    scopes: List[str] = []
    service_type: Optional[str] = None  # "user", "service", "ai_agent"
    tenant_id: Optional[str] = None
    exp: Optional[datetime] = None


class ServiceIdentity(BaseModel):
    """Service identity for service-to-service authentication."""
    service_id: str
    service_name: str
    service_type: str  # "ai_agent", "workflow_engine", "external_api"
    tenant_id: Optional[str] = None
    permissions: List[str] = []


class AuthenticationService:
    """
    Comprehensive authentication service for JWT handling and service security.
    
    Provides token generation, validation, and service identity management
    for AI workflows and external integrations.
    """
    
    def __init__(self):
        """Initialize the authentication service."""
        self.settings = get_settings()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # OAuth2 scheme for token extraction
        self.oauth2_scheme = OAuth2PasswordBearer(
            tokenUrl="api/v1/auth/token",
            scopes={
                "read": "Read access to resources",
                "write": "Write access to resources", 
                "admin": "Administrative access",
                "ai:execute": "Execute AI workflows",
                "ai:manage": "Manage AI agents and workflows",
                "external:read": "Read from external platforms",
                "external:write": "Write to external platforms"
            }
        )
        
        # Predefined service identities for internal components
        self.service_registry: Dict[str, ServiceIdentity] = {
            "ai_research_agent": ServiceIdentity(
                service_id="ai_research_agent",
                service_name="AI Research Agent",
                service_type="ai_agent",
                permissions=["read", "ai:execute", "external:read"]
            ),
            "workflow_engine": ServiceIdentity(
                service_id="workflow_engine",
                service_name="Temporal Workflow Engine",
                service_type="workflow_engine",
                permissions=["read", "write", "ai:execute", "ai:manage"]
            ),
            "campaign_analyzer": ServiceIdentity(
                service_id="campaign_analyzer",
                service_name="Campaign Analysis Agent",
                service_type="ai_agent",
                permissions=["read", "ai:execute", "external:read"]
            ),
            "integration_hub": ServiceIdentity(
                service_id="integration_hub",
                service_name="External Platform Integration Hub",
                service_type="external_api",
                permissions=["external:read", "external:write"]
            )
        }
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
        scopes: List[str] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time
            scopes: List of permission scopes
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        # Set expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        # Add standard claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.settings.PROJECT_NAME,
            "scopes": scopes or []
        })
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                self.settings.SECRET_KEY,
                algorithm=self.settings.ALGORITHM
            )
            logger.info(f"Created access token for subject: {data.get('sub', 'unknown')}")
            return encoded_jwt
            
        except Exception as e:
            logger.error(f"Error creating access token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating access token"
            )
    
    def verify_token(self, token: str) -> TokenData:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenData with decoded payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.settings.ALGORITHM]
            )
            
            # Extract token data
            subject: str = payload.get("sub")
            scopes: List[str] = payload.get("scopes", [])
            service_type: str = payload.get("service_type")
            tenant_id: str = payload.get("tenant_id")
            exp_timestamp: int = payload.get("exp")
            
            if subject is None:
                raise credentials_exception
                
            # Convert expiration timestamp to datetime
            exp = datetime.fromtimestamp(exp_timestamp) if exp_timestamp else None
            
            token_data = TokenData(
                sub=subject,
                scopes=scopes,
                service_type=service_type,
                tenant_id=tenant_id,
                exp=exp
            )
            
            logger.debug(f"Token verified for subject: {subject}")
            return token_data
            
        except JWTError as e:
            logger.warning(f"JWT validation error: {str(e)}")
            raise credentials_exception
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise credentials_exception
    
    def create_service_token(
        self,
        service_id: str,
        tenant_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT token for service-to-service authentication.
        
        Args:
            service_id: Service identifier from registry
            tenant_id: Optional tenant ID for multi-tenant access
            expires_delta: Token expiration time
            
        Returns:
            JWT token for service authentication
            
        Raises:
            HTTPException: If service is not registered
        """
        if service_id not in self.service_registry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown service ID: {service_id}"
            )
        
        service = self.service_registry[service_id]
        
        # Create token data for service
        token_data = {
            "sub": service_id,
            "service_type": "service",
            "service_name": service.service_name,
            "service_category": service.service_type,
            "tenant_id": tenant_id
        }
        
        # Use longer expiration for service tokens
        if expires_delta is None:
            expires_delta = timedelta(hours=24)  # 24 hour service tokens
        
        return self.create_access_token(
            data=token_data,
            expires_delta=expires_delta,
            scopes=service.permissions
        )
    
    def verify_service_identity(self, token_data: TokenData) -> ServiceIdentity:
        """
        Verify that a token represents a valid service identity.
        
        Args:
            token_data: Decoded token data
            
        Returns:
            ServiceIdentity for the service
            
        Raises:
            HTTPException: If service identity is invalid
        """
        if token_data.service_type != "service":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid service type for service authentication"
            )
        
        service_id = token_data.sub
        if service_id not in self.service_registry:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unknown service identity"
            )
        
        service_identity = self.service_registry[service_id]
        
        # Add tenant context if present
        if token_data.tenant_id:
            service_identity.tenant_id = token_data.tenant_id
        
        logger.info(f"Service identity verified: {service_id}")
        return service_identity
    
    def check_permissions(self, token_data: TokenData, required_scopes: List[str]) -> bool:
        """
        Check if token has required permission scopes.
        
        Args:
            token_data: Decoded token data
            required_scopes: List of required permission scopes
            
        Returns:
            True if all required scopes are present
        """
        token_scopes = set(token_data.scopes)
        required_scopes_set = set(required_scopes)
        
        has_permissions = required_scopes_set.issubset(token_scopes)
        
        if not has_permissions:
            missing_scopes = required_scopes_set - token_scopes
            logger.warning(
                f"Missing permissions for {token_data.sub}: {missing_scopes}"
            )
        
        return has_permissions
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """
        Generate password hash.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        try:
            return self.pwd_context.hash(password)
        except Exception as e:
            logger.error(f"Password hashing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing password"
            )
    
    def generate_api_key(self, prefix: str = "mp") -> str:
        """
        Generate a secure API key for external integrations.
        
        Args:
            prefix: API key prefix
            
        Returns:
            Secure API key string
        """
        # Generate 32 bytes of random data
        random_bytes = secrets.token_bytes(32)
        # Convert to URL-safe base64 and remove padding
        api_key = secrets.token_urlsafe(32)
        return f"{prefix}_{api_key}"
    
    def validate_api_key_format(self, api_key: str) -> bool:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if format is valid
        """
        try:
            # Check basic format: prefix_base64string
            parts = api_key.split("_", 1)
            if len(parts) != 2:
                return False
            
            prefix, key_part = parts
            
            # Check prefix length and content
            if len(prefix) < 2 or not prefix.isalnum():
                return False
            
            # Check key part length (should be ~43 chars for 32 bytes base64)
            if len(key_part) < 40:
                return False
            
            return True
            
        except Exception:
            return False


# Global authentication service instance
auth_service = AuthenticationService()


def get_auth_service() -> AuthenticationService:
    """Get authentication service instance - useful for dependency injection."""
    return auth_service


# Dependency for token extraction and validation
async def get_current_token(token: str = None) -> Optional[str]:
    """Extract token from request - used by other dependencies."""
    return token


async def get_current_user(token: str = None) -> TokenData:
    """
    Get current user/service from JWT token.
    
    Returns:
        TokenData with user/service information
        
    Raises:
        HTTPException: If token is invalid
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_service.verify_token(token)


def require_scopes(required_scopes: List[str]):
    """
    Decorator to require specific permission scopes.
    
    Args:
        required_scopes: List of required permission scopes
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract token_data from kwargs (should be injected by FastAPI)
            token_data = kwargs.get('token_data') or kwargs.get('current_user')
            
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not auth_service.check_permissions(token_data, required_scopes):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_scopes}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_service_identity():
    """
    Decorator to require service identity authentication.
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            token_data = kwargs.get('token_data') or kwargs.get('current_user')
            
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Service authentication required"
                )
            
            # Verify service identity
            service_identity = auth_service.verify_service_identity(token_data)
            
            # Add service identity to kwargs
            kwargs['service_identity'] = service_identity
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator 