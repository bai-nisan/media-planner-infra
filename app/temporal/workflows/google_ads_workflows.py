"""
Google Ads integration workflows for the media planning platform.

These workflows orchestrate Google Ads data synchronization, campaign management,
and reporting activities with proper error handling and retry mechanisms.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Import activities
from app.temporal.activities.google_ads_activities import (
    authenticate_google_ads,
    fetch_google_ads_campaigns,
    fetch_google_ads_keywords,
    fetch_google_ads_reports,
    transform_google_ads_data,
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
class GoogleAdsIntegrationWorkflow:
    """
    Main Google Ads integration workflow for complete data synchronization.
    
    This workflow handles authentication, data fetching, transformation,
    validation, and storage of Google Ads data.
    """
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        credentials: Dict[str, Any],
        tenant_id: str,
        sync_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the complete Google Ads integration process.
        
        Args:
            account_id: Google Ads account ID
            credentials: Authentication credentials
            tenant_id: Tenant identifier
            sync_config: Synchronization configuration
            
        Returns:
            Integration result with data summary and status
        """
        integration_id = f"google_ads_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Log integration start
            await workflow.execute_activity(
                log_integration_event,
                "start",
                integration_id,
                {
                    "account_id": account_id,
                    "tenant_id": tenant_id,
                    "sync_config": sync_config
                },
                tenant_id,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            )
            
            # Step 1: Authenticate with Google Ads
            workflow.logger.info(f"Starting Google Ads authentication for account {account_id}")
            auth_data = await workflow.execute_activity(
                authenticate_google_ads,
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
            
            # Step 2: Fetch campaign data
            workflow.logger.info("Fetching Google Ads campaigns")
            campaigns = await workflow.execute_activity(
                fetch_google_ads_campaigns,
                auth_data,
                sync_config.get("date_range"),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=5,
                )
            )
            
            # Step 3: Fetch keyword data for campaigns
            workflow.logger.info("Fetching Google Ads keywords")
            campaign_ids = [campaign["campaign_id"] for campaign in campaigns]
            keywords = await workflow.execute_activity(
                fetch_google_ads_keywords,
                auth_data,
                campaign_ids,
                sync_config.get("date_range"),
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=5,
                )
            )
            
            # Step 4: Generate reports if configured
            reports = []
            if sync_config.get("include_reports", False):
                workflow.logger.info("Generating Google Ads reports")
                reports = await workflow.execute_activity(
                    fetch_google_ads_reports,
                    auth_data,
                    sync_config.get("report_type", "CAMPAIGN"),
                    sync_config.get("date_range", {"start_date": "2024-01-01", "end_date": "2024-12-31"}),
                    sync_config.get("report_fields", ["impressions", "clicks", "cost"]),
                    start_to_close_timeout=timedelta(minutes=20),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=10),
                        maximum_interval=timedelta(minutes=10),
                        maximum_attempts=3,
                    )
                )
            
            # Step 5: Transform data to platform format
            workflow.logger.info("Transforming Google Ads data")
            raw_data = {
                "account_id": account_id,
                "campaigns": campaigns,
                "keywords": keywords,
                "reports": reports
            }
            
            transformed_data = await workflow.execute_activity(
                transform_google_ads_data,
                raw_data,
                sync_config.get("transformation_config", {}),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=3,
                )
            )
            
            # Step 6: Validate data integrity
            workflow.logger.info("Validating data integrity")
            validation_result = await workflow.execute_activity(
                validate_data_integrity,
                transformed_data,
                sync_config.get("validation_rules", {}),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            )
            
            # Step 7: Store data if validation passed
            storage_result = None
            if validation_result["is_valid"]:
                workflow.logger.info("Storing integration data")
                storage_result = await workflow.execute_activity(
                    store_integration_data,
                    transformed_data,
                    sync_config.get("storage_config", {}),
                    tenant_id,
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_interval=timedelta(minutes=2),
                        maximum_attempts=3,
                    )
                )
            else:
                workflow.logger.warning(f"Data validation failed: {validation_result['errors']}")
            
            # Step 8: Send success notification
            integration_result = {
                "integration_id": integration_id,
                "status": "success" if validation_result["is_valid"] else "validation_failed",
                "account_id": account_id,
                "tenant_id": tenant_id,
                "data_summary": {
                    "campaigns_fetched": len(campaigns),
                    "keywords_fetched": len(keywords),
                    "reports_generated": len(reports),
                    "validation_status": validation_result["is_valid"],
                    "storage_status": storage_result["success"] if storage_result else False
                },
                "validation_result": validation_result,
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
            # Send notification
            await workflow.execute_activity(
                send_notification,
                "success" if validation_result["is_valid"] else "warning",
                f"Google Ads integration completed for account {account_id}",
                sync_config.get("notification_recipients", []),
                {"integration_result": integration_result},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                )
            )
            
            # Log success
            await workflow.execute_activity(
                log_integration_event,
                "success",
                integration_id,
                integration_result,
                tenant_id,
                start_to_close_timeout=timedelta(minutes=1)
            )
            
            return integration_result
            
        except Exception as e:
            # Handle errors with recovery strategies
            workflow.logger.error(f"Google Ads integration failed: {str(e)}")
            
            error_info = {
                "type": type(e).__name__,
                "message": str(e),
                "integration_id": integration_id,
                "account_id": account_id
            }
            
            integration_context = {
                "integration_id": integration_id,
                "tenant_id": tenant_id,
                "account_id": account_id,
                "workflow_type": "GoogleAdsIntegrationWorkflow"
            }
            
            # Handle the error
            error_handling_result = await workflow.execute_activity(
                handle_integration_error,
                error_info,
                integration_context,
                sync_config.get("recovery_options", {}),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=2,
                )
            )
            
            # Send error notification
            await workflow.execute_activity(
                send_notification,
                "error",
                f"Google Ads integration failed for account {account_id}: {str(e)}",
                sync_config.get("notification_recipients", []),
                {"error": error_info, "error_handling": error_handling_result},
                start_to_close_timeout=timedelta(minutes=2)
            )
            
            # Return error result
            return {
                "integration_id": integration_id,
                "status": "error",
                "account_id": account_id,
                "tenant_id": tenant_id,
                "error": error_info,
                "error_handling": error_handling_result,
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class GoogleAdsCampaignSyncWorkflow:
    """
    Focused workflow for syncing Google Ads campaign data only.
    
    This is a lighter workflow for regular campaign updates without
    the full integration overhead.
    """
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        auth_data: Dict[str, Any],
        tenant_id: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Sync Google Ads campaign data.
        
        Args:
            account_id: Google Ads account ID
            auth_data: Pre-authenticated session data
            tenant_id: Tenant identifier
            date_range: Optional date range for data
            
        Returns:
            Sync result with campaign data
        """
        sync_id = f"campaign_sync_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Fetch campaigns
            campaigns = await workflow.execute_activity(
                fetch_google_ads_campaigns,
                auth_data,
                date_range,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=3,
                )
            )
            
            # Transform and validate
            transformed_data = await workflow.execute_activity(
                transform_google_ads_data,
                {"account_id": account_id, "campaigns": campaigns},
                {},
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            # Store results
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
            workflow.logger.error(f"Campaign sync failed: {str(e)}")
            return {
                "sync_id": sync_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class GoogleAdsReportingWorkflow:
    """
    Dedicated workflow for generating Google Ads reports.
    
    This workflow handles complex report generation with custom
    parameters and scheduling capabilities.
    """
    
    @workflow.run
    async def run(
        self,
        account_id: str,
        auth_data: Dict[str, Any],
        report_config: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Generate Google Ads reports.
        
        Args:
            account_id: Google Ads account ID
            auth_data: Pre-authenticated session data
            report_config: Report configuration parameters
            tenant_id: Tenant identifier
            
        Returns:
            Report generation result
        """
        report_id = f"report_{account_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Generate report
            report_data = await workflow.execute_activity(
                fetch_google_ads_reports,
                auth_data,
                report_config["report_type"],
                report_config["date_range"],
                report_config["fields"],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=10),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=3,
                )
            )
            
            # Transform and store
            transformed_report = await workflow.execute_activity(
                transform_google_ads_data,
                {"account_id": account_id, "reports": [report_data]},
                report_config.get("transformation_config", {}),
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            storage_result = await workflow.execute_activity(
                store_integration_data,
                transformed_report,
                {"table": "reports", "report_id": report_id},
                tenant_id,
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            return {
                "report_id": report_id,
                "status": "success",
                "report_data": report_data,
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Report generation failed: {str(e)}")
            return {
                "report_id": report_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            } 