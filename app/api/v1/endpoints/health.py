"""
Health check endpoints for monitoring and status verification.
"""

from fastapi import APIRouter, status
from app.core.config import settings

router = APIRouter()


@router.get("/ping", status_code=status.HTTP_200_OK)
async def ping():
    """Simple ping endpoint for load balancer health checks."""
    return {"message": "pong"}


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_status():
    """Detailed status endpoint with system information."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    } 