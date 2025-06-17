"""
Meta Ads integration workflows for the media planning platform.

These workflows orchestrate Meta Ads data synchronization, campaign management,
and insights activities with proper error handling and retry mechanisms.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
from app.temporal.activities.meta_ads_activities import (
    authenticate_meta_ads,
    fetch_meta_ads_campaigns,
    fetch_meta_ads_insights,
    fetch_meta_ads_audiences,
    transform_meta_ads_data,
)
from app.temporal.activities.common_activities import (
    validate_data_integrity,
    store_integration_data,
    send_notification,
    log_integration_event,
    handle_integration_error,
)

logger = logging.getLogger(__name__)


@workflow.defn
class MetaAdsIntegrationWorkflow:
    """Main Meta Ads integration workflow for complete data synchronization."""
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        credentials: Dict[str, Any],
        tenant_id: str,
        sync_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the complete Meta Ads integration process."""
        integration_id = f"meta_ads_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Step 1: Authenticate
            auth_data = await workflow.execute_activity(
                authenticate_meta_ads,
                account_id,
                credentials,
                tenant_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=3,
                )
            )
            
            # Step 2: Fetch campaigns
            campaigns = await workflow.execute_activity(
                fetch_meta_ads_campaigns,
                auth_data,
                sync_config.get("date_range"),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=5,
                )
            )
            
            # Step 3: Fetch insights if configured
            insights = []
            if sync_config.get("include_insights", False):
                insights = await workflow.execute_activity(
                    fetch_meta_ads_insights,
                    auth_data,
                    sync_config.get("insights_level", "campaign"),
                    sync_config.get("date_range", {"start_date": "2024-01-01", "end_date": "2024-12-31"}),
                    sync_config.get("metrics", ["impressions", "clicks", "spend"]),
                    start_to_close_timeout=timedelta(minutes=20)
                )
            
            # Step 4: Transform data
            raw_data = {
                "account_id": account_id,
                "campaigns": campaigns,
                "insights": insights
            }
            
            transformed_data = await workflow.execute_activity(
                transform_meta_ads_data,
                raw_data,
                sync_config.get("transformation_config", {}),
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            # Step 5: Validate and store
            validation_result = await workflow.execute_activity(
                validate_data_integrity,
                transformed_data,
                sync_config.get("validation_rules", {}),
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            storage_result = None
            if validation_result["is_valid"]:
                storage_result = await workflow.execute_activity(
                    store_integration_data,
                    transformed_data,
                    sync_config.get("storage_config", {}),
                    tenant_id,
                    start_to_close_timeout=timedelta(minutes=10)
                )
            
            return {
                "integration_id": integration_id,
                "status": "success" if validation_result["is_valid"] else "validation_failed",
                "account_id": account_id,
                "tenant_id": tenant_id,
                "data_summary": {
                    "campaigns_fetched": len(campaigns),
                    "insights_fetched": len(insights),
                    "validation_status": validation_result["is_valid"],
                    "storage_status": storage_result["success"] if storage_result else False
                },
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Meta Ads integration failed: {str(e)}")
            return {
                "integration_id": integration_id,
                "status": "error",
                "account_id": account_id,
                "tenant_id": tenant_id,
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class MetaAdsCampaignSyncWorkflow:
    """Focused workflow for syncing Meta Ads campaign data only."""
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        auth_data: Dict[str, Any],
        tenant_id: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Sync Meta Ads campaign data."""
        sync_id = f"meta_campaign_sync_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            campaigns = await workflow.execute_activity(
                fetch_meta_ads_campaigns,
                auth_data,
                date_range,
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            transformed_data = await workflow.execute_activity(
                transform_meta_ads_data,
                {"account_id": account_id, "campaigns": campaigns},
                {},
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            storage_result = await workflow.execute_activity(
                store_integration_data,
                transformed_data,
                {"table": "campaigns", "upsert": True},
                tenant_id,
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            return {
                "sync_id": sync_id,
                "status": "success",
                "campaigns_synced": len(campaigns),
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Meta campaign sync failed: {str(e)}")
            return {
                "sync_id": sync_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class MetaAdsInsightsWorkflow:
    """Dedicated workflow for generating Meta Ads insights."""
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        auth_data: Dict[str, Any],
        insights_config: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Generate Meta Ads insights."""
        insights_id = f"meta_insights_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            insights_data = await workflow.execute_activity(
                fetch_meta_ads_insights,
                auth_data,
                insights_config["level"],
                insights_config["date_range"],
                insights_config["metrics"],
                start_to_close_timeout=timedelta(minutes=30)
            )
            
            transformed_insights = await workflow.execute_activity(
                transform_meta_ads_data,
                {"account_id": account_id, "insights": [insights_data]},
                insights_config.get("transformation_config", {}),
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            storage_result = await workflow.execute_activity(
                store_integration_data,
                transformed_insights,
                {"table": "insights", "insights_id": insights_id},
                tenant_id,
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            return {
                "insights_id": insights_id,
                "status": "success",
                "insights_data": insights_data,
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Meta insights generation failed: {str(e)}")
            return {
                "insights_id": insights_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            } 