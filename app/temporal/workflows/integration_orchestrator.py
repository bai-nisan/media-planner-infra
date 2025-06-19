"""
Integration orchestrator workflows for coordinating multi-platform synchronization.

These workflows handle coordination between different platform integrations,
cross-platform data validation, and comprehensive integration monitoring.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Import common activities
from app.temporal.activities.common_activities import (
    handle_integration_error,
    log_integration_event,
    send_notification,
    store_integration_data,
    validate_data_integrity,
)

# Import workflows
from .google_ads_workflows import GoogleAdsIntegrationWorkflow
from .google_drive_workflows import GoogleDriveIntegrationWorkflow
from .meta_ads_workflows import MetaAdsIntegrationWorkflow

logger = logging.getLogger(__name__)


@workflow.defn
class PlatformIntegrationOrchestratorWorkflow:
    """
    Main orchestrator workflow for coordinating multiple platform integrations.

    This workflow manages the execution of multiple platform integrations
    in parallel or sequence, handles cross-platform data validation,
    and provides unified reporting.
    """

    @workflow.run
    async def run(
        self, integration_config: Dict[str, Any], tenant_id: str
    ) -> Dict[str, Any]:
        """
        Orchestrate multiple platform integrations.

        Args:
            integration_config: Configuration for all platforms to integrate
            tenant_id: Tenant identifier

        Returns:
            Orchestration result with status of all integrations
        """
        orchestration_id = (
            f"orchestration_{tenant_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        )

        try:
            # Log orchestration start
            await workflow.execute_activity(
                log_integration_event,
                "orchestration_start",
                orchestration_id,
                {
                    "tenant_id": tenant_id,
                    "platforms": list(integration_config.get("platforms", {}).keys()),
                    "execution_mode": integration_config.get(
                        "execution_mode", "parallel"
                    ),
                },
                tenant_id,
                start_to_close_timeout=timedelta(minutes=1),
            )

            execution_mode = integration_config.get("execution_mode", "parallel")
            platforms = integration_config.get("platforms", {})
            integration_results = {}

            if execution_mode == "parallel":
                # Execute all integrations in parallel
                workflow.logger.info("Starting parallel platform integrations")
                integration_handles = []

                # Start Google Ads integration if configured
                if "google_ads" in platforms:
                    google_ads_config = platforms["google_ads"]
                    google_ads_handle = workflow.start_child_workflow(
                        GoogleAdsIntegrationWorkflow.run,
                        google_ads_config["account_id"],
                        google_ads_config["credentials"],
                        tenant_id,
                        google_ads_config.get("sync_config", {}),
                        id=f"google_ads_{orchestration_id}",
                        task_queue="media-planner-integration",
                    )
                    integration_handles.append(("google_ads", google_ads_handle))

                # Start Meta Ads integration if configured
                if "meta_ads" in platforms:
                    meta_ads_config = platforms["meta_ads"]
                    meta_ads_handle = workflow.start_child_workflow(
                        MetaAdsIntegrationWorkflow.run,
                        meta_ads_config["account_id"],
                        meta_ads_config["credentials"],
                        tenant_id,
                        meta_ads_config.get("sync_config", {}),
                        id=f"meta_ads_{orchestration_id}",
                        task_queue="media-planner-integration",
                    )
                    integration_handles.append(("meta_ads", meta_ads_handle))

                # Start Google Drive integration if configured
                if "google_drive" in platforms:
                    drive_config = platforms["google_drive"]
                    drive_handle = workflow.start_child_workflow(
                        GoogleDriveIntegrationWorkflow.run,
                        drive_config["credentials"],
                        tenant_id,
                        drive_config.get("sync_config", {}),
                        id=f"google_drive_{orchestration_id}",
                        task_queue="media-planner-integration",
                    )
                    integration_handles.append(("google_drive", drive_handle))

                # Wait for all integrations to complete
                for platform, handle in integration_handles:
                    try:
                        result = await handle
                        integration_results[platform] = result
                        workflow.logger.info(
                            f"{platform} integration completed: {result['status']}"
                        )
                    except Exception as e:
                        workflow.logger.error(
                            f"{platform} integration failed: {str(e)}"
                        )
                        integration_results[platform] = {
                            "status": "error",
                            "error": str(e),
                            "failed_at": workflow.now().isoformat(),
                        }

            else:
                # Execute integrations sequentially
                workflow.logger.info("Starting sequential platform integrations")

                for platform, config in platforms.items():
                    try:
                        workflow.logger.info(f"Starting {platform} integration")

                        if platform == "google_ads":
                            result = await workflow.execute_child_workflow(
                                GoogleAdsIntegrationWorkflow.run,
                                config["account_id"],
                                config["credentials"],
                                tenant_id,
                                config.get("sync_config", {}),
                                id=f"google_ads_{orchestration_id}",
                                task_queue="media-planner-integration",
                            )
                        elif platform == "meta_ads":
                            result = await workflow.execute_child_workflow(
                                MetaAdsIntegrationWorkflow.run,
                                config["account_id"],
                                config["credentials"],
                                tenant_id,
                                config.get("sync_config", {}),
                                id=f"meta_ads_{orchestration_id}",
                                task_queue="media-planner-integration",
                            )
                        elif platform == "google_drive":
                            result = await workflow.execute_child_workflow(
                                GoogleDriveIntegrationWorkflow.run,
                                config["credentials"],
                                tenant_id,
                                config.get("sync_config", {}),
                                id=f"google_drive_{orchestration_id}",
                                task_queue="media-planner-integration",
                            )
                        else:
                            workflow.logger.warning(f"Unknown platform: {platform}")
                            continue

                        integration_results[platform] = result
                        workflow.logger.info(
                            f"{platform} integration completed: {result['status']}"
                        )

                        # Stop on first failure if configured
                        if (
                            config.get("stop_on_failure", False)
                            and result["status"] == "error"
                        ):
                            break

                    except Exception as e:
                        workflow.logger.error(
                            f"{platform} integration failed: {str(e)}"
                        )
                        integration_results[platform] = {
                            "status": "error",
                            "error": str(e),
                            "failed_at": workflow.now().isoformat(),
                        }

                        # Stop on failure if configured
                        if config.get("stop_on_failure", False):
                            break

            # Calculate overall status
            successful_integrations = [
                p for p, r in integration_results.items() if r["status"] == "success"
            ]
            failed_integrations = [
                p for p, r in integration_results.items() if r["status"] == "error"
            ]

            overall_status = (
                "success"
                if len(failed_integrations) == 0
                else (
                    "partial_success" if len(successful_integrations) > 0 else "error"
                )
            )

            # Create orchestration result
            orchestration_result = {
                "orchestration_id": orchestration_id,
                "status": overall_status,
                "tenant_id": tenant_id,
                "execution_mode": execution_mode,
                "platforms_requested": list(platforms.keys()),
                "platforms_successful": successful_integrations,
                "platforms_failed": failed_integrations,
                "integration_results": integration_results,
                "summary": {
                    "total_platforms": len(platforms),
                    "successful_platforms": len(successful_integrations),
                    "failed_platforms": len(failed_integrations),
                    "success_rate": (
                        len(successful_integrations) / len(platforms)
                        if platforms
                        else 0
                    ),
                },
                "completed_at": workflow.now().isoformat(),
            }

            # Send notification
            notification_type = (
                "success"
                if overall_status == "success"
                else ("warning" if overall_status == "partial_success" else "error")
            )

            await workflow.execute_activity(
                send_notification,
                notification_type,
                f"Platform integration orchestration completed with status: {overall_status}",
                integration_config.get("notification_recipients", []),
                {"orchestration_result": orchestration_result},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                ),
            )

            # Log completion
            await workflow.execute_activity(
                log_integration_event,
                "orchestration_complete",
                orchestration_id,
                orchestration_result,
                tenant_id,
                start_to_close_timeout=timedelta(minutes=1),
            )

            return orchestration_result

        except Exception as e:
            workflow.logger.error(f"Orchestration failed: {str(e)}")

            error_result = {
                "orchestration_id": orchestration_id,
                "status": "error",
                "tenant_id": tenant_id,
                "error": str(e),
                "failed_at": workflow.now().isoformat(),
            }

            # Send error notification
            await workflow.execute_activity(
                send_notification,
                "error",
                f"Platform integration orchestration failed: {str(e)}",
                integration_config.get("notification_recipients", []),
                {"error_result": error_result},
                start_to_close_timeout=timedelta(minutes=2),
            )

            return error_result


@workflow.defn
class MultiPlatformDataSyncWorkflow:
    """
    Simplified workflow for regular multi-platform data synchronization.

    This workflow performs lighter, more frequent syncs across platforms
    without the full integration overhead.
    """

    @workflow.run
    async def run(
        self, platforms: List[str], tenant_id: str, sync_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform multi-platform data sync.

        Args:
            platforms: List of platforms to sync
            tenant_id: Tenant identifier
            sync_config: Sync configuration

        Returns:
            Sync result summary
        """
        sync_id = f"multi_sync_{tenant_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            sync_results = {}

            # For this simplified version, we'll just log the sync operation
            # In a real implementation, this would call the lightweight sync workflows
            for platform in platforms:
                workflow.logger.info(f"Syncing {platform} data")

                # Mock sync result
                sync_results[platform] = {
                    "status": "success",
                    "records_synced": 100,  # Mock data
                    "sync_duration": "30s",
                    "last_sync": workflow.now().isoformat(),
                }

            return {
                "sync_id": sync_id,
                "status": "success",
                "platforms_synced": platforms,
                "sync_results": sync_results,
                "completed_at": workflow.now().isoformat(),
            }

        except Exception as e:
            workflow.logger.error(f"Multi-platform sync failed: {str(e)}")
            return {
                "sync_id": sync_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat(),
            }


@workflow.defn
class IntegrationHealthCheckWorkflow:
    """
    Health check workflow for monitoring integration system status.

    This workflow performs periodic health checks on all integration
    components and reports system status.
    """

    @workflow.run
    async def run(
        self, tenant_id: str, health_check_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform integration system health check.

        Args:
            tenant_id: Tenant identifier
            health_check_config: Health check configuration

        Returns:
            Health check result
        """
        health_check_id = (
            f"health_check_{tenant_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        )

        try:
            # Mock health check results
            # In a real implementation, this would check:
            # - Database connectivity
            # - API endpoint availability
            # - Authentication status
            # - Recent integration success rates
            # - Resource utilization

            health_status = {
                "health_check_id": health_check_id,
                "overall_status": "healthy",
                "tenant_id": tenant_id,
                "components": {
                    "database": {"status": "healthy", "response_time_ms": 50},
                    "google_ads_api": {"status": "healthy", "response_time_ms": 200},
                    "meta_ads_api": {"status": "healthy", "response_time_ms": 180},
                    "google_drive_api": {"status": "healthy", "response_time_ms": 120},
                    "temporal_cluster": {"status": "healthy", "worker_count": 5},
                },
                "metrics": {
                    "integrations_last_24h": 25,
                    "success_rate": 0.96,
                    "average_duration_minutes": 15.5,
                    "data_freshness_hours": 2.0,
                },
                "checked_at": workflow.now().isoformat(),
            }

            # Send notification if unhealthy
            if health_status["overall_status"] != "healthy":
                await workflow.execute_activity(
                    send_notification,
                    "warning",
                    f"Integration system health check detected issues",
                    health_check_config.get("notification_recipients", []),
                    {"health_status": health_status},
                    start_to_close_timeout=timedelta(minutes=2),
                )

            return health_status

        except Exception as e:
            workflow.logger.error(f"Health check failed: {str(e)}")
            return {
                "health_check_id": health_check_id,
                "overall_status": "error",
                "tenant_id": tenant_id,
                "error": str(e),
                "failed_at": workflow.now().isoformat(),
            }
