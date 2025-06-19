"""
Main API router for v1 endpoints.

Includes all endpoint routers and organizes API structure.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    auth,
    campaigns,
    database,
    health,
    tenants,
    websocket,
    workflows,
)

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(database.router, prefix="/database", tags=["database"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(
    campaigns.router, prefix="/tenants/{tenant_id}/campaigns", tags=["campaigns"]
)
api_router.include_router(websocket.router, tags=["websocket", "real-time"])
api_router.include_router(
    agents.router, prefix="/agents", tags=["agents", "multi-agent-system"]
)

api_router.include_router(
    workflows.router, prefix="/workflows", tags=["workflows", "data-extraction"]
)
