"""
Data Workflows API Endpoints

Provides REST API endpoints for orchestrating data extraction and transformation workflows.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.core.config import get_settings, Settings
from app.dependencies import get_current_user, get_tenant_context
from app.services.data_workflows import (
    DataWorkflowService, 
    get_data_workflow_service,
    WorkflowContext,
    CampaignFile,
    StandardizedCampaign,
    SyncResult,
    DataTransformationResult
)
from app.schemas.base import BaseResponse


logger = logging.getLogger(__name__)
router = APIRouter()


class WorkflowRequest(BaseModel):
    """Request model for workflow operations."""
    folder_id: Optional[str] = Field(None, description="Specific Google Drive folder ID to search")
    search_keywords: Optional[List[str]] = Field(None, description="Keywords to search for in file names")
    update_sheets: bool = Field(False, description="Whether to write results back to sheets")
    discover_files: bool = Field(True, description="Whether to discover new files")


class FileDiscoveryRequest(BaseModel):
    """Request model for file discovery."""
    folder_id: Optional[str] = None
    search_keywords: Optional[List[str]] = None


class FileDiscoveryResponse(BaseResponse):
    """Response model for file discovery."""
    files: List[CampaignFile]
    total_files: int


class TransformationResponse(BaseResponse):
    """Response model for data transformation."""
    result: DataTransformationResult


class SyncResponse(BaseResponse):
    """Response model for sync operations."""
    result: SyncResult


class WorkflowStatusResponse(BaseResponse):
    """Response model for workflow status."""
    workflow_id: str
    status: str
    started_at: datetime
    tenant_id: str
    progress: dict


@router.post("/discover-files", response_model=FileDiscoveryResponse)
async def discover_campaign_files(
    request: FileDiscoveryRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    workflow_service: DataWorkflowService = Depends(get_data_workflow_service)
):
    """
    Discover campaign-related files in Google Drive.
    
    This endpoint searches for files that contain campaign-related keywords
    and returns metadata about discovered files.
    """
    try:
        # Create workflow context
        context = WorkflowContext(
            tenant_id=tenant_id,
            user_id=current_user.get("sub", "unknown"),
            workflow_id=f"discover_{int(datetime.utcnow().timestamp())}",
            started_at=datetime.utcnow(),
            settings={}
        )
        
        # Discover files
        discovered_files = await workflow_service.discover_campaign_files(
            context=context,
            search_keywords=request.search_keywords,
            folder_id=request.folder_id
        )
        
        return FileDiscoveryResponse(
            success=True,
            message=f"Discovered {len(discovered_files)} campaign files",
            files=discovered_files,
            total_files=len(discovered_files)
        )
        
    except Exception as e:
        logger.error(f"File discovery failed for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File discovery failed: {str(e)}"
        )


@router.post("/sync", response_model=SyncResponse)
async def sync_data(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    workflow_service: DataWorkflowService = Depends(get_data_workflow_service)
):
    """
    Perform bidirectional data synchronization.
    
    This endpoint orchestrates the complete data pipeline:
    1. Discovers campaign files in Google Drive
    2. Extracts data from Google Sheets
    3. Transforms data to standardized format
    4. Optionally writes back to sheets
    """
    try:
        # Create workflow context
        context = WorkflowContext(
            tenant_id=tenant_id,
            user_id=current_user.get("sub", "unknown"),
            workflow_id=f"sync_{int(datetime.utcnow().timestamp())}",
            started_at=datetime.utcnow(),
            settings={}
        )
        
        # Execute sync workflow
        sync_result = await workflow_service.sync_data_bidirectional(
            context=context,
            discover_files=request.discover_files,
            update_sheets=request.update_sheets,
            folder_id=request.folder_id
        )
        
        # Log the sync result for audit purposes
        logger.info(
            f"Sync completed for tenant {tenant_id}: "
            f"{sync_result.campaigns_transformed} campaigns processed"
        )
        
        return SyncResponse(
            success=sync_result.success,
            message=f"Sync completed: {sync_result.campaigns_transformed} campaigns processed",
            result=sync_result
        )
        
    except Exception as e:
        logger.error(f"Data sync failed for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data sync failed: {str(e)}"
        )


@router.post("/sync-async", response_model=WorkflowStatusResponse)
async def sync_data_async(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    workflow_service: DataWorkflowService = Depends(get_data_workflow_service)
):
    """
    Start asynchronous bidirectional data synchronization.
    
    This endpoint starts a background sync process and returns immediately
    with a workflow ID that can be used to check progress.
    """
    try:
        workflow_id = f"sync_{tenant_id}_{int(datetime.utcnow().timestamp())}"
        
        # Create workflow context
        context = WorkflowContext(
            tenant_id=tenant_id,
            user_id=current_user.get("sub", "unknown"),
            workflow_id=workflow_id,
            started_at=datetime.utcnow(),
            settings={}
        )
        
        # Add background task
        background_tasks.add_task(
            _execute_sync_workflow,
            workflow_service,
            context,
            request
        )
        
        return WorkflowStatusResponse(
            success=True,
            message=f"Sync workflow {workflow_id} started",
            workflow_id=workflow_id,
            status="running",
            started_at=context.started_at,
            tenant_id=tenant_id,
            progress={"phase": "starting", "progress_percent": 0}
        )
        
    except Exception as e:
        logger.error(f"Failed to start async sync for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync workflow: {str(e)}"
        )


@router.get("/health")
async def workflow_health():
    """
    Check the health of workflow services.
    
    This endpoint verifies that all required services and dependencies
    are available for workflow execution.
    """
    try:
        # Basic health check - ensure we can import required services
        from app.services.google.auth import GoogleAuthManager
        from app.services.google.drive_client import GoogleDriveClient
        from app.services.google.sheets_client import GoogleSheetsClient
        
        return {
            "status": "healthy",
            "service": "data-workflows",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "google_auth": "available",
                "drive_client": "available", 
                "sheets_client": "available",
                "workflow_service": "available"
            }
        }
        
    except Exception as e:
        logger.error(f"Workflow health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Workflow services are not healthy: {str(e)}"
        )


async def _execute_sync_workflow(
    workflow_service: DataWorkflowService,
    context: WorkflowContext,
    request: WorkflowRequest
) -> None:
    """
    Background task to execute sync workflow.
    
    This function runs the complete sync workflow in the background
    and logs the results for later retrieval.
    """
    try:
        logger.info(f"Starting background sync workflow {context.workflow_id}")
        
        sync_result = await workflow_service.sync_data_bidirectional(
            context=context,
            discover_files=request.discover_files,
            update_sheets=request.update_sheets,
            folder_id=request.folder_id
        )
        
        # Log completion
        logger.info(
            f"Background sync {context.workflow_id} completed: "
            f"success={sync_result.success}, "
            f"campaigns={sync_result.campaigns_transformed}, "
            f"time={sync_result.execution_time_seconds:.2f}s"
        )
        
        # In a production system, you would store the result in a database
        # or cache for later retrieval via a status endpoint
        
    except Exception as e:
        logger.error(f"Background sync {context.workflow_id} failed: {e}")


# Dependency injection for DataWorkflowService
def get_data_workflow_service_dependency(
    settings: Settings = Depends(get_settings)
) -> DataWorkflowService:
    """Dependency to get DataWorkflowService instance."""
    return get_data_workflow_service(settings) 