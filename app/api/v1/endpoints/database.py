"""
Database endpoints for AI workflow data access and health monitoring.

Provides health checks and context data endpoints for AI workflows.
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.database import get_database_bridge, DatabaseBridge

router = APIRouter()


@router.get("/health", response_model=Dict[str, Any])
async def database_health_check(
    db_bridge: DatabaseBridge = Depends(get_database_bridge)
) -> Dict[str, Any]:
    """
    Check database connection health.
    
    Returns:
        Database health status and connection information
    """
    health_status = await db_bridge.health_check()
    
    # Return appropriate HTTP status based on health
    if health_status.get("status") == "healthy":
        return health_status
    else:
        return JSONResponse(
            status_code=503,
            content=health_status
        )


@router.get("/campaign-context/{campaign_id}", response_model=Optional[Dict[str, Any]])
async def get_campaign_context(
    campaign_id: str,
    tenant_id: Optional[str] = Query(None, description="Tenant ID for multi-tenant access"),
    db_bridge: DatabaseBridge = Depends(get_database_bridge)
) -> Optional[Dict[str, Any]]:
    """
    Get campaign context data for AI workflows.
    
    Args:
        campaign_id: Campaign identifier
        tenant_id: Optional tenant identifier for multi-tenant access
        
    Returns:
        Campaign context data or 404 if not found
    """
    try:
        context = db_bridge.get_campaign_context(campaign_id, tenant_id)
        
        if context is None:
            raise HTTPException(
                status_code=404,
                detail=f"Campaign not found: {campaign_id}"
            )
            
        return context
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving campaign context: {str(e)}"
        )


@router.get("/tenant-context/{tenant_id}", response_model=Optional[Dict[str, Any]])
async def get_tenant_context(
    tenant_id: str,
    db_bridge: DatabaseBridge = Depends(get_database_bridge)
) -> Optional[Dict[str, Any]]:
    """
    Get tenant context data for AI workflows.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Tenant context data or 404 if not found
    """
    try:
        context = db_bridge.get_tenant_context(tenant_id)
        
        if context is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant not found: {tenant_id}"
            )
            
        return context
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving tenant context: {str(e)}"
        )


@router.get("/workflow-history/{workflow_type}", response_model=List[Dict[str, Any]])
async def get_workflow_history(
    workflow_type: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    db_bridge: DatabaseBridge = Depends(get_database_bridge)
) -> List[Dict[str, Any]]:
    """
    Get workflow execution history for AI learning.
    
    Args:
        workflow_type: Type of workflow to retrieve history for
        limit: Maximum number of records to return (1-100)
        
    Returns:
        List of workflow execution records
    """
    try:
        history = db_bridge.get_workflow_history(workflow_type, limit)
        return history
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving workflow history: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_database_cache(
    db_bridge: DatabaseBridge = Depends(get_database_bridge)
) -> Dict[str, str]:
    """
    Clear database cache.
    
    Returns:
        Success message
    """
    try:
        db_bridge.clear_cache()
        return {"message": "Database cache cleared successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache: {str(e)}"
        ) 