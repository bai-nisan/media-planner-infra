"""
Temporal Sync Workflows for Media Planning Platform

This module provides scheduled, periodic synchronization workflows that build upon
the integration workflows. Implements cron-like scheduling using Temporal's
scheduling features with data validation and conflict resolution.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from temporalio import workflow
from temporalio.common import RetryPolicy

from ..activities.common_activities import (
    load_sync_checkpoint,
    log_sync_event,
    resolve_data_conflicts,
    send_notification,
    store_sync_checkpoint,
    validate_sync_data,
)
from .google_ads_workflows import (
    GoogleAdsCampaignSyncWorkflow,
    GoogleAdsIntegrationWorkflow,
)
from .google_drive_workflows import (
    GoogleDriveFileSyncWorkflow,
    GoogleDriveIntegrationWorkflow,
)
from .integration_orchestrator import PlatformIntegrationOrchestratorWorkflow
from .meta_ads_workflows import MetaAdsCampaignSyncWorkflow, MetaAdsIntegrationWorkflow


@workflow.defn
class ScheduledSyncWorkflow:
    """
    Core scheduled synchronization workflow that manages periodic data sync
    across all platforms with configurable intervals and retry policies.
    """

    @workflow.run
    async def run(self, sync_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scheduled synchronization across configured platforms.

        Args:
            sync_config: Configuration containing:
                - tenant_id: Multi-tenant identifier
                - platforms: List of platforms to sync ['google_ads', 'meta_ads', 'google_drive']
                - sync_interval: Sync frequency in minutes (default: 60)
                - full_sync_interval: Full sync frequency in hours (default: 24)
                - conflict_resolution: Strategy for handling conflicts
                - notification_settings: Where to send sync status updates
                - retry_policy: Custom retry configuration
        """

        tenant_id = sync_config["tenant_id"]
        platforms = sync_config.get(
            "platforms", ["google_ads", "meta_ads", "google_drive"]
        )
        sync_interval = sync_config.get("sync_interval", 60)  # minutes
        full_sync_interval = sync_config.get("full_sync_interval", 24)  # hours

        workflow.logger.info(
            f"Starting scheduled sync for tenant {tenant_id} across platforms: {platforms}"
        )

        # Log sync start event
        await workflow.execute_activity(
            log_sync_event,
            {
                "tenant_id": tenant_id,
                "event_type": "scheduled_sync_start",
                "platforms": platforms,
                "sync_interval": sync_interval,
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        sync_results = {}

        # Load last sync checkpoint to determine sync type needed
        checkpoint = await workflow.execute_activity(
            load_sync_checkpoint,
            {"tenant_id": tenant_id},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        is_full_sync = self._should_do_full_sync(checkpoint, full_sync_interval)

        try:
            # Execute sync for each platform
            for platform in platforms:
                platform_result = await self._sync_platform(
                    platform, tenant_id, is_full_sync, sync_config
                )
                sync_results[platform] = platform_result

                # Small delay between platforms to avoid rate limiting
                await asyncio.sleep(2)

            # Validate synchronized data across platforms
            validation_result = await workflow.execute_activity(
                validate_sync_data,
                {
                    "tenant_id": tenant_id,
                    "sync_results": sync_results,
                    "validation_rules": sync_config.get("validation_rules", {}),
                },
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            # Handle conflicts if any found during validation
            if validation_result.get("conflicts"):
                conflict_resolution = await workflow.execute_activity(
                    resolve_data_conflicts,
                    {
                        "tenant_id": tenant_id,
                        "conflicts": validation_result["conflicts"],
                        "resolution_strategy": sync_config.get(
                            "conflict_resolution", "latest_wins"
                        ),
                    },
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                sync_results["conflict_resolution"] = conflict_resolution

            # Store successful sync checkpoint
            await workflow.execute_activity(
                store_sync_checkpoint,
                {
                    "tenant_id": tenant_id,
                    "sync_results": sync_results,
                    "sync_type": "full" if is_full_sync else "incremental",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            # Send success notification
            await workflow.execute_activity(
                send_notification,
                {
                    "tenant_id": tenant_id,
                    "notification_type": "sync_success",
                    "message": f"Scheduled sync completed successfully for {len(platforms)} platforms",
                    "details": sync_results,
                    "recipients": sync_config.get("notification_settings", {}).get(
                        "success", []
                    ),
                },
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            workflow.logger.info(
                f"Scheduled sync completed successfully for tenant {tenant_id}"
            )
            return {
                "status": "success",
                "tenant_id": tenant_id,
                "sync_results": sync_results,
                "sync_type": "full" if is_full_sync else "incremental",
                "platforms_synced": platforms,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            workflow.logger.error(
                f"Scheduled sync failed for tenant {tenant_id}: {str(e)}"
            )

            # Send error notification
            await workflow.execute_activity(
                send_notification,
                {
                    "tenant_id": tenant_id,
                    "notification_type": "sync_error",
                    "message": f"Scheduled sync failed: {str(e)}",
                    "details": {"error": str(e), "partial_results": sync_results},
                    "recipients": sync_config.get("notification_settings", {}).get(
                        "error", []
                    ),
                },
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            raise

    def _should_do_full_sync(
        self, checkpoint: Dict[str, Any], full_sync_interval: int
    ) -> bool:
        """Determine if a full sync is needed based on checkpoint data."""
        if not checkpoint or not checkpoint.get("last_full_sync"):
            return True

        last_full_sync = datetime.fromisoformat(checkpoint["last_full_sync"])
        time_since_full = datetime.utcnow() - last_full_sync

        return time_since_full.total_seconds() > (full_sync_interval * 3600)

    async def _sync_platform(
        self,
        platform: str,
        tenant_id: str,
        is_full_sync: bool,
        sync_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute sync for a specific platform."""

        workflow.logger.info(
            f"Starting {platform} sync (full={is_full_sync}) for tenant {tenant_id}"
        )

        platform_config = {
            "tenant_id": tenant_id,
            "full_sync": is_full_sync,
            **sync_config.get(f"{platform}_config", {}),
        }

        if platform == "google_ads":
            if is_full_sync:
                return await workflow.execute_child_workflow(
                    GoogleAdsIntegrationWorkflow.run,
                    platform_config,
                    id=f"google-ads-full-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            else:
                return await workflow.execute_child_workflow(
                    GoogleAdsCampaignSyncWorkflow.run,
                    platform_config,
                    id=f"google-ads-incremental-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=15),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

        elif platform == "meta_ads":
            if is_full_sync:
                return await workflow.execute_child_workflow(
                    MetaAdsIntegrationWorkflow.run,
                    platform_config,
                    id=f"meta-ads-full-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            else:
                return await workflow.execute_child_workflow(
                    MetaAdsCampaignSyncWorkflow.run,
                    platform_config,
                    id=f"meta-ads-incremental-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=15),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

        elif platform == "google_drive":
            if is_full_sync:
                return await workflow.execute_child_workflow(
                    GoogleDriveIntegrationWorkflow.run,
                    platform_config,
                    id=f"google-drive-full-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=20),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            else:
                return await workflow.execute_child_workflow(
                    GoogleDriveFileSyncWorkflow.run,
                    platform_config,
                    id=f"google-drive-incremental-sync-{tenant_id}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

        else:
            raise ValueError(f"Unsupported platform: {platform}")


@workflow.defn
class MultiTenantSyncOrchestratorWorkflow:
    """
    Orchestrates scheduled synchronization across multiple tenants,
    managing resource allocation and prioritization.
    """

    @workflow.run
    async def run(self, orchestrator_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scheduled sync across multiple tenants with resource management.

        Args:
            orchestrator_config: Configuration containing:
                - tenants: List of tenant configurations
                - max_concurrent_syncs: Maximum parallel syncs
                - priority_levels: Tenant priority mapping
                - resource_limits: CPU/memory constraints
        """

        tenants = orchestrator_config["tenants"]
        max_concurrent = orchestrator_config.get("max_concurrent_syncs", 3)

        workflow.logger.info(
            f"Starting multi-tenant sync orchestration for {len(tenants)} tenants"
        )

        # Group tenants by priority
        prioritized_tenants = self._prioritize_tenants(tenants, orchestrator_config)

        all_results = {}

        # Process tenants in priority groups with concurrency limits
        for priority_group in prioritized_tenants:
            group_results = await self._process_tenant_group(
                priority_group, max_concurrent, orchestrator_config
            )
            all_results.update(group_results)

        workflow.logger.info(
            f"Multi-tenant sync orchestration completed for {len(tenants)} tenants"
        )

        return {
            "status": "completed",
            "total_tenants": len(tenants),
            "successful_syncs": len(
                [r for r in all_results.values() if r.get("status") == "success"]
            ),
            "failed_syncs": len(
                [r for r in all_results.values() if r.get("status") == "failed"]
            ),
            "results": all_results,
            "completed_at": datetime.utcnow().isoformat(),
        }

    def _prioritize_tenants(
        self, tenants: List[Dict], config: Dict
    ) -> List[List[Dict]]:
        """Group tenants by priority levels."""
        priority_levels = config.get("priority_levels", {})
        groups = {"high": [], "medium": [], "low": []}

        for tenant in tenants:
            tenant_id = tenant["tenant_id"]
            priority = priority_levels.get(tenant_id, "medium")
            groups[priority].append(tenant)

        # Return in order: high, medium, low priority
        return [groups["high"], groups["medium"], groups["low"]]

    async def _process_tenant_group(
        self, tenant_group: List[Dict], max_concurrent: int, config: Dict
    ) -> Dict[str, Any]:
        """Process a group of tenants with concurrency control."""

        if not tenant_group:
            return {}

        results = {}

        # Process tenants in batches of max_concurrent
        for i in range(0, len(tenant_group), max_concurrent):
            batch = tenant_group[i : i + max_concurrent]

            # Start sync workflows for this batch
            batch_tasks = []
            for tenant_config in batch:
                task = workflow.execute_child_workflow(
                    ScheduledSyncWorkflow.run,
                    tenant_config,
                    id=f"scheduled-sync-{tenant_config['tenant_id']}-{workflow.now()}",
                    task_queue="media-planner-sync-queue",
                    execution_timeout=timedelta(hours=2),
                    retry_policy=RetryPolicy(
                        maximum_attempts=1
                    ),  # Handle retries at tenant level
                )
                batch_tasks.append((tenant_config["tenant_id"], task))

            # Wait for batch completion
            for tenant_id, task in batch_tasks:
                try:
                    result = await task
                    results[tenant_id] = result
                except Exception as e:
                    workflow.logger.error(
                        f"Sync failed for tenant {tenant_id}: {str(e)}"
                    )
                    results[tenant_id] = {
                        "status": "failed",
                        "tenant_id": tenant_id,
                        "error": str(e),
                        "failed_at": datetime.utcnow().isoformat(),
                    }

        return results


@workflow.defn
class ConflictResolutionWorkflow:
    """
    Specialized workflow for handling data conflicts during synchronization.
    Implements various resolution strategies and escalation paths.
    """

    @workflow.run
    async def run(self, conflict_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve data conflicts found during synchronization.

        Args:
            conflict_config: Configuration containing:
                - tenant_id: Multi-tenant identifier
                - conflicts: List of detected conflicts
                - resolution_strategy: How to handle conflicts
                - escalation_rules: When to escalate to manual review
        """

        tenant_id = conflict_config["tenant_id"]
        conflicts = conflict_config["conflicts"]
        strategy = conflict_config.get("resolution_strategy", "latest_wins")

        workflow.logger.info(
            f"Starting conflict resolution for tenant {tenant_id} with {len(conflicts)} conflicts"
        )

        resolved_conflicts = []
        escalated_conflicts = []

        for conflict in conflicts:
            try:
                # Attempt automatic resolution
                resolution_result = await workflow.execute_activity(
                    resolve_data_conflicts,
                    {
                        "tenant_id": tenant_id,
                        "conflicts": [conflict],
                        "resolution_strategy": strategy,
                    },
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                if resolution_result.get("auto_resolved"):
                    resolved_conflicts.append(
                        {
                            "conflict": conflict,
                            "resolution": resolution_result,
                            "resolved_at": datetime.utcnow().isoformat(),
                        }
                    )
                else:
                    # Escalate complex conflicts
                    escalated_conflicts.append(conflict)

            except Exception as e:
                workflow.logger.error(
                    f"Failed to resolve conflict {conflict.get('id', 'unknown')}: {str(e)}"
                )
                escalated_conflicts.append(conflict)

        # Handle escalated conflicts
        if escalated_conflicts:
            await workflow.execute_activity(
                send_notification,
                {
                    "tenant_id": tenant_id,
                    "notification_type": "conflict_escalation",
                    "message": f"{len(escalated_conflicts)} conflicts require manual review",
                    "details": {"escalated_conflicts": escalated_conflicts},
                    "recipients": conflict_config.get("escalation_rules", {}).get(
                        "recipients", []
                    ),
                },
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

        workflow.logger.info(
            f"Conflict resolution completed: {len(resolved_conflicts)} resolved, {len(escalated_conflicts)} escalated"
        )

        return {
            "status": "completed",
            "tenant_id": tenant_id,
            "total_conflicts": len(conflicts),
            "resolved_conflicts": resolved_conflicts,
            "escalated_conflicts": escalated_conflicts,
            "resolution_strategy": strategy,
            "completed_at": datetime.utcnow().isoformat(),
        }


@workflow.defn
class SyncHealthMonitorWorkflow:
    """
    Monitors the health and performance of synchronization operations.
    Provides alerts for failures, performance degradation, and system issues.
    """

    @workflow.run
    async def run(self, monitor_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitor sync health across all tenants and platforms.

        Args:
            monitor_config: Configuration containing:
                - monitoring_interval: How often to check health (minutes)
                - alert_thresholds: Performance and error thresholds
                - notification_settings: Where to send alerts
        """

        monitoring_interval = monitor_config.get("monitoring_interval", 15)  # minutes

        workflow.logger.info(
            f"Starting sync health monitoring with {monitoring_interval}min interval"
        )

        # This workflow runs continuously
        while True:
            try:
                # Check system health
                health_check_result = await workflow.execute_activity(
                    log_sync_event,
                    {
                        "tenant_id": "system",
                        "event_type": "health_check",
                        "check_timestamp": datetime.utcnow().isoformat(),
                    },
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                # Analyze metrics and send alerts if needed
                if health_check_result.get("alerts_needed"):
                    await workflow.execute_activity(
                        send_notification,
                        {
                            "tenant_id": "system",
                            "notification_type": "health_alert",
                            "message": "Sync system health issues detected",
                            "details": health_check_result,
                            "recipients": monitor_config.get(
                                "notification_settings", {}
                            ).get("health_alerts", []),
                        },
                        start_to_close_timeout=timedelta(minutes=3),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )

                # Wait for next check interval
                await asyncio.sleep(monitoring_interval * 60)

            except Exception as e:
                workflow.logger.error(f"Health monitoring check failed: {str(e)}")
                await asyncio.sleep(60)  # Short retry interval on error
