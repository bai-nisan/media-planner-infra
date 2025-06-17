"""
Main API router for v1 endpoints.

Includes all endpoint routers and organizes API structure.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, campaigns, tenants

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(
    tenants.router,
    prefix="/tenants",
    tags=["tenants"]
)
api_router.include_router(
    campaigns.router,
    prefix="/tenants/{tenant_id}/campaigns",
    tags=["campaigns"]
) 