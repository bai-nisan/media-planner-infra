"""
Dependency injection functions for FastAPI.

This module provides dependency injection functions for various services
including Temporal workflow management, database connections, and auth.
"""

from fastapi import HTTPException, Request, Depends
from typing import Optional, Generator
import logging

from app.services.temporal_service import TemporalService
from app.services.google import (
    GoogleAuthManager, 
    GoogleDriveClient, 
    GoogleSheetsClient, 
    GoogleAdsClient
)
from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)


def get_temporal_service(request: Request) -> TemporalService:
    """
    Get the Temporal service instance from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TemporalService: The Temporal service instance
        
    Raises:
        HTTPException: If Temporal service is not available
    """
    if not hasattr(request.app.state, 'temporal_service') or request.app.state.temporal_service is None:
        raise HTTPException(
            status_code=503,
            detail="Temporal service is not available"
        )
    return request.app.state.temporal_service


def get_temporal_client(request: Request):
    """
    Get the Temporal client instance from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TemporalClient: The Temporal client instance
        
    Raises:
        HTTPException: If Temporal client is not available
    """
    if not hasattr(request.app.state, 'temporal_client') or request.app.state.temporal_client is None:
        raise HTTPException(
            status_code=503,
            detail="Temporal client is not available"
        )
    return request.app.state.temporal_client


def get_tenant_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    """
    Extract tenant ID from request headers.
    
    Args:
        request: FastAPI request object
        settings: Application settings
        
    Returns:
        str: Tenant ID
    """
    tenant_id = request.headers.get(settings.TENANT_HEADER_NAME)
    if not tenant_id:
        # Use default tenant if no header provided
        tenant_id = settings.DEFAULT_TENANT_ID
    
    return tenant_id


def get_user_id(request: Request) -> Optional[str]:
    """
    Extract user ID from request context (after authentication).
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[str]: User ID if authenticated, None otherwise
    """
    # This would typically come from JWT token or session
    # For now, return None as auth is not yet implemented
    user = getattr(request.state, 'user', None)
    return user.id if user else None


async def verify_temporal_health(temporal_service: TemporalService = Depends(get_temporal_service)) -> bool:
    """
    Verify that Temporal service is healthy.
    
    Args:
        temporal_service: Temporal service instance
        
    Returns:
        bool: True if healthy
        
    Raises:
        HTTPException: If Temporal is unhealthy
    """
    health_status = await temporal_service.health_check()
    
    if health_status.get("status") != "healthy":
        raise HTTPException(
            status_code=503,
            detail=f"Temporal service is unhealthy: {health_status}"
        )
    
    return True


# Google API Service Dependencies

def get_google_auth_manager(settings: Settings = Depends(get_settings)) -> GoogleAuthManager:
    """
    Get Google Auth Manager instance.
    
    Args:
        settings: Application settings
        
    Returns:
        GoogleAuthManager: Auth manager instance
    """
    return GoogleAuthManager(settings)


def get_google_drive_client(
    auth_manager: GoogleAuthManager = Depends(get_google_auth_manager),
    settings: Settings = Depends(get_settings)
) -> Generator[GoogleDriveClient, None, None]:
    """
    Get Google Drive client instance with proper lifecycle management.
    
    Args:
        auth_manager: Google auth manager
        settings: Application settings
        
    Yields:
        GoogleDriveClient: Drive client instance
    """
    client = GoogleDriveClient(auth_manager, settings)
    try:
        yield client
    except Exception as e:
        logger.error(f"Error during Drive client operation: {e}")
        raise
    finally:
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing Drive client: {e}")


def get_google_sheets_client(
    auth_manager: GoogleAuthManager = Depends(get_google_auth_manager),
    settings: Settings = Depends(get_settings)
) -> Generator[GoogleSheetsClient, None, None]:
    """
    Get Google Sheets client instance with proper lifecycle management.
    
    Args:
        auth_manager: Google auth manager
        settings: Application settings
        
    Yields:
        GoogleSheetsClient: Sheets client instance
    """
    client = GoogleSheetsClient(auth_manager, settings)
    try:
        yield client
    except Exception as e:
        logger.error(f"Error during Sheets client operation: {e}")
        raise
    finally:
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing Sheets client: {e}")


def get_google_ads_client(
    auth_manager: GoogleAuthManager = Depends(get_google_auth_manager),
    settings: Settings = Depends(get_settings)
) -> Generator[GoogleAdsClient, None, None]:
    """
    Get Google Ads client instance with proper lifecycle management.
    
    Args:
        auth_manager: Google auth manager
        settings: Application settings
        
    Yields:
        GoogleAdsClient: Ads client instance
    """
    client = GoogleAdsClient(auth_manager, settings)
    try:
        yield client
    except Exception as e:
        logger.error(f"Error during Ads client operation: {e}")
        raise
    finally:
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing Ads client: {e}")


def verify_google_auth(
    auth_manager: GoogleAuthManager = Depends(get_google_auth_manager)
) -> GoogleAuthManager:
    """
    Verify Google authentication is available.
    
    Args:
        auth_manager: Google auth manager
        
    Returns:
        GoogleAuthManager: Verified auth manager
        
    Raises:
        HTTPException: If authentication is not available
    """
    if not auth_manager.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Google authentication required. Please connect your Google account."
        )
    
    return auth_manager 