"""
Temporal service layer for workflow management.

This module provides high-level business operations for managing
Temporal workflows related to media planning, integration, and data sync.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import uuid4

from app.temporal.client import TemporalClient
from app.core.config import Settings

logger = logging.getLogger(__name__)


class MediaPlanningWorkflowService:
    """
    Service for managing media planning workflows.
    
    This service provides high-level operations for triggering and managing
    workflows related to media planning, campaign analysis, and optimization.
    """
    
    def __init__(self, temporal_client: TemporalClient, settings: Settings):
        self.temporal_client = temporal_client
        self.settings = settings
    
    async def start_campaign_analysis(
        self,
        campaign_id: str,
        tenant_id: str,
        user_id: str,
        analysis_params: Dict[str, Any]
    ) -> str:
        """
        Start a campaign analysis workflow.
        
        Args:
            campaign_id: ID of the campaign to analyze
            tenant_id: Tenant identifier
            user_id: User who requested the analysis
            analysis_params: Parameters for the analysis
            
        Returns:
            str: Workflow execution ID
        """
        workflow_id = f"campaign-analysis-{campaign_id}-{uuid4().hex[:8]}"
        
        try:
            # Import workflow here to avoid circular imports
            from app.temporal.workflows.planning import CampaignAnalysisWorkflow
            
            # Prepare workflow input
            workflow_input = {
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "analysis_params": analysis_params,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Start the workflow
            handle = await self.temporal_client.start_workflow(
                CampaignAnalysisWorkflow,
                workflow_input,
                workflow_id=workflow_id,
                task_queue=self.settings.TEMPORAL_TASK_QUEUE_PLANNING,
                memo={
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id
                },
                search_attributes={
                    "CampaignId": campaign_id,
                    "TenantId": tenant_id,
                    "WorkflowType": "CampaignAnalysis"
                }
            )
            
            logger.info(f"Started campaign analysis workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start campaign analysis workflow: {e}")
            raise
    
    async def start_budget_optimization(
        self,
        campaign_id: str,
        tenant_id: str,
        optimization_goals: Dict[str, Any]
    ) -> str:
        """
        Start a budget optimization workflow.
        
        Args:
            campaign_id: ID of the campaign to optimize
            tenant_id: Tenant identifier
            optimization_goals: Optimization parameters and goals
            
        Returns:
            str: Workflow execution ID
        """
        workflow_id = f"budget-optimization-{campaign_id}-{uuid4().hex[:8]}"
        
        try:
            from app.temporal.workflows.planning import BudgetOptimizationWorkflow
            
            workflow_input = {
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "optimization_goals": optimization_goals,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            handle = await self.temporal_client.start_workflow(
                BudgetOptimizationWorkflow,
                workflow_input,
                workflow_id=workflow_id,
                task_queue=self.settings.TEMPORAL_TASK_QUEUE_PLANNING,
                memo={
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id
                },
                search_attributes={
                    "CampaignId": campaign_id,
                    "TenantId": tenant_id,
                    "WorkflowType": "BudgetOptimization"
                }
            )
            
            logger.info(f"Started budget optimization workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start budget optimization workflow: {e}")
            raise


class IntegrationWorkflowService:
    """
    Service for managing integration workflows.
    
    This service handles workflows for integrating with external platforms
    like Google Ads, Meta Ads, and Google Drive.
    """
    
    def __init__(self, temporal_client: TemporalClient, settings: Settings):
        self.temporal_client = temporal_client
        self.settings = settings
    
    async def start_platform_sync(
        self,
        platform: str,
        tenant_id: str,
        sync_params: Dict[str, Any]
    ) -> str:
        """
        Start a platform synchronization workflow.
        
        Args:
            platform: Platform to sync (google_ads, meta_ads, google_drive)
            tenant_id: Tenant identifier
            sync_params: Synchronization parameters
            
        Returns:
            str: Workflow execution ID
        """
        workflow_id = f"platform-sync-{platform}-{tenant_id}-{uuid4().hex[:8]}"
        
        try:
            from app.temporal.workflows.integration import PlatformSyncWorkflow
            
            workflow_input = {
                "platform": platform,
                "tenant_id": tenant_id,
                "sync_params": sync_params,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            handle = await self.temporal_client.start_workflow(
                PlatformSyncWorkflow,
                workflow_input,
                workflow_id=workflow_id,
                task_queue=self.settings.TEMPORAL_TASK_QUEUE_INTEGRATION,
                memo={
                    "platform": platform,
                    "tenant_id": tenant_id
                },
                search_attributes={
                    "Platform": platform,
                    "TenantId": tenant_id,
                    "WorkflowType": "PlatformSync"
                }
            )
            
            logger.info(f"Started platform sync workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start platform sync workflow: {e}")
            raise
    
    async def start_data_import(
        self,
        source: str,
        tenant_id: str,
        import_config: Dict[str, Any]
    ) -> str:
        """
        Start a data import workflow.
        
        Args:
            source: Data source identifier
            tenant_id: Tenant identifier
            import_config: Import configuration
            
        Returns:
            str: Workflow execution ID
        """
        workflow_id = f"data-import-{source}-{tenant_id}-{uuid4().hex[:8]}"
        
        try:
            from app.temporal.workflows.integration import DataImportWorkflow
            
            workflow_input = {
                "source": source,
                "tenant_id": tenant_id,
                "import_config": import_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            handle = await self.temporal_client.start_workflow(
                DataImportWorkflow,
                workflow_input,
                workflow_id=workflow_id,
                task_queue=self.settings.TEMPORAL_TASK_QUEUE_INTEGRATION,
                memo={
                    "source": source,
                    "tenant_id": tenant_id
                },
                search_attributes={
                    "Source": source,
                    "TenantId": tenant_id,
                    "WorkflowType": "DataImport"
                }
            )
            
            logger.info(f"Started data import workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start data import workflow: {e}")
            raise


class SyncWorkflowService:
    """
    Service for managing data synchronization workflows.
    
    This service handles periodic and on-demand data synchronization
    between different systems and platforms.
    """
    
    def __init__(self, temporal_client: TemporalClient, settings: Settings):
        self.temporal_client = temporal_client
        self.settings = settings
    
    async def start_scheduled_sync(
        self,
        sync_type: str,
        tenant_id: str,
        schedule_config: Dict[str, Any]
    ) -> str:
        """
        Start a scheduled synchronization workflow.
        
        Args:
            sync_type: Type of synchronization
            tenant_id: Tenant identifier
            schedule_config: Schedule configuration
            
        Returns:
            str: Workflow execution ID
        """
        workflow_id = f"scheduled-sync-{sync_type}-{tenant_id}-{uuid4().hex[:8]}"
        
        try:
            from app.temporal.workflows.sync import ScheduledSyncWorkflow
            
            workflow_input = {
                "sync_type": sync_type,
                "tenant_id": tenant_id,
                "schedule_config": schedule_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            handle = await self.temporal_client.start_workflow(
                ScheduledSyncWorkflow,
                workflow_input,
                workflow_id=workflow_id,
                task_queue=self.settings.TEMPORAL_TASK_QUEUE_SYNC,
                memo={
                    "sync_type": sync_type,
                    "tenant_id": tenant_id
                },
                search_attributes={
                    "SyncType": sync_type,
                    "TenantId": tenant_id,
                    "WorkflowType": "ScheduledSync"
                }
            )
            
            logger.info(f"Started scheduled sync workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start scheduled sync workflow: {e}")
            raise


class WorkflowManagementService:
    """
    Service for managing workflow execution and monitoring.
    
    This service provides operations for monitoring, controlling,
    and managing workflow executions.
    """
    
    def __init__(self, temporal_client: TemporalClient, settings: Settings):
        self.temporal_client = temporal_client
        self.settings = settings
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow execution.
        
        Args:
            workflow_id: Workflow execution ID
            
        Returns:
            Dict[str, Any]: Workflow status information
        """
        try:
            handle = await self.temporal_client.get_workflow_handle(workflow_id)
            
            # Get workflow description
            description = await handle.describe()
            
            status_info = {
                "workflow_id": workflow_id,
                "status": description.status.name,
                "start_time": description.start_time.isoformat() if description.start_time else None,
                "execution_time": description.execution_time.isoformat() if description.execution_time else None,
                "close_time": description.close_time.isoformat() if description.close_time else None,
                "task_queue": description.task_queue,
                "workflow_type": description.workflow_type,
                "memo": description.memo,
                "search_attributes": description.search_attributes
            }
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get workflow status for {workflow_id}: {e}")
            raise
    
    async def cancel_workflow(self, workflow_id: str, reason: str = "User requested") -> bool:
        """
        Cancel a running workflow.
        
        Args:
            workflow_id: Workflow execution ID
            reason: Cancellation reason
            
        Returns:
            bool: True if successful
        """
        try:
            handle = await self.temporal_client.get_workflow_handle(workflow_id)
            await handle.cancel()
            
            logger.info(f"Cancelled workflow {workflow_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
            return False
    
    async def list_workflows_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List workflows for a specific tenant.
        
        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of results
            status_filter: Optional status filter
            
        Returns:
            List[Dict[str, Any]]: List of workflow information
        """
        try:
            # Build query
            query = f"TenantId = '{tenant_id}'"
            if status_filter:
                query += f" AND ExecutionStatus = '{status_filter}'"
            
            workflows = []
            count = 0
            
            async for workflow in self.temporal_client.list_workflows(query, limit):
                if count >= limit:
                    break
                
                workflow_info = {
                    "workflow_id": workflow.execution.workflow_id,
                    "workflow_type": workflow.workflow_type,
                    "status": workflow.status.name,
                    "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
                    "close_time": workflow.close_time.isoformat() if workflow.close_time else None,
                    "memo": workflow.memo,
                    "search_attributes": workflow.search_attributes
                }
                
                workflows.append(workflow_info)
                count += 1
            
            return workflows
            
        except Exception as e:
            logger.error(f"Failed to list workflows for tenant {tenant_id}: {e}")
            raise


class TemporalService:
    """
    Main Temporal service that aggregates all workflow services.
    
    This service provides a unified interface for all Temporal operations
    in the media planning platform.
    """
    
    def __init__(self, temporal_client: TemporalClient, settings: Settings):
        self.temporal_client = temporal_client
        self.settings = settings
        
        # Initialize sub-services
        self.media_planning = MediaPlanningWorkflowService(temporal_client, settings)
        self.integration = IntegrationWorkflowService(temporal_client, settings)
        self.sync = SyncWorkflowService(temporal_client, settings)
        self.management = WorkflowManagementService(temporal_client, settings)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of Temporal services.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            # Check Temporal client connection
            client_healthy = await self.temporal_client.health_check()
            
            # Get basic system info
            if client_healthy:
                try:
                    # Try to list a small number of workflows
                    workflow_count = 0
                    async for _ in self.temporal_client.list_workflows("", 1):
                        workflow_count += 1
                        break
                    
                    list_workflows_healthy = True
                except Exception:
                    list_workflows_healthy = False
            else:
                list_workflows_healthy = False
            
            health_status = {
                "status": "healthy" if client_healthy and list_workflows_healthy else "unhealthy",
                "temporal_client": "connected" if client_healthy else "disconnected",
                "workflow_listing": "working" if list_workflows_healthy else "failed",
                "namespace": self.settings.TEMPORAL_NAMESPACE,
                "server_address": self.settings.temporal_address,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Temporal health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            } 