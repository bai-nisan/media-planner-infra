"""
Temporal Schedulers for Media Planning Platform

This module provides cron-like scheduling capabilities using Temporal's
scheduling features to manage periodic synchronization workflows.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from temporalio import workflow
from temporalio.client import Client, Schedule, ScheduleHandle
from temporalio.common import RetryPolicy

from .workflows.sync_workflows import (
    ScheduledSyncWorkflow,
    MultiTenantSyncOrchestratorWorkflow,
    SyncHealthMonitorWorkflow
)


class SyncScheduler:
    """
    Manages scheduled synchronization workflows using Temporal's scheduling features.
    Provides cron-like scheduling with dynamic configuration.
    """
    
    def __init__(self, client: Client):
        self.client = client
        self.active_schedules: Dict[str, ScheduleHandle] = {}
    
    async def create_tenant_sync_schedule(
        self,
        tenant_id: str,
        sync_config: Dict[str, Any],
        schedule_config: Dict[str, Any]
    ) -> ScheduleHandle:
        """
        Create a scheduled sync for a specific tenant.
        
        Args:
            tenant_id: Unique tenant identifier
            sync_config: Configuration for the sync workflow
            schedule_config: Scheduling configuration (cron expression, timezone, etc.)
            
        Returns:
            Handle to the created schedule
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        # Create the schedule with cron expression
        schedule = Schedule(
            action=Schedule.Action(
                workflow=ScheduledSyncWorkflow.run,
                args=[sync_config],
                id=f"sync-{tenant_id}-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                task_queue="media-planner-sync-queue",
                execution_timeout=timedelta(hours=2),
                retry_policy=RetryPolicy(maximum_attempts=3)
            ),
            spec=Schedule.Spec(
                cron_expressions=[schedule_config.get("cron", "0 */1 * * *")],  # Every hour by default
                timezone=schedule_config.get("timezone", "UTC"),
                start_at=schedule_config.get("start_at"),
                end_at=schedule_config.get("end_at"),
                jitter=timedelta(minutes=schedule_config.get("jitter_minutes", 5))
            ),
            policy=Schedule.Policy(
                overlap=Schedule.OverlapPolicy.SKIP,  # Skip if previous run is still running
                catchup_window=timedelta(minutes=schedule_config.get("catchup_window_minutes", 60)),
                pause_on_failure=schedule_config.get("pause_on_failure", True)
            )
        )
        
        # Create the schedule
        schedule_handle = await self.client.create_schedule(
            schedule_id,
            schedule,
            note=f"Scheduled sync for tenant {tenant_id}",
            search_attributes={"tenant_id": tenant_id, "schedule_type": "sync"}
        )
        
        self.active_schedules[schedule_id] = schedule_handle
        
        print(f"Created sync schedule for tenant {tenant_id}: {schedule_id}")
        return schedule_handle
    
    async def create_multi_tenant_sync_schedule(
        self,
        tenants: List[Dict[str, Any]],
        schedule_config: Dict[str, Any]
    ) -> ScheduleHandle:
        """
        Create a schedule for multi-tenant synchronization orchestration.
        
        Args:
            tenants: List of tenant configurations
            schedule_config: Scheduling configuration
            
        Returns:
            Handle to the created schedule
        """
        
        schedule_id = "multi-tenant-sync-orchestrator"
        
        orchestrator_config = {
            "tenants": tenants,
            "max_concurrent_syncs": schedule_config.get("max_concurrent", 5),
            "priority_levels": schedule_config.get("priority_levels", {}),
            "resource_limits": schedule_config.get("resource_limits", {})
        }
        
        # Create the schedule for orchestration
        schedule = Schedule(
            action=Schedule.Action(
                workflow=MultiTenantSyncOrchestratorWorkflow.run,
                args=[orchestrator_config],
                id=f"multi-tenant-sync-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                task_queue="media-planner-sync-queue",
                execution_timeout=timedelta(hours=4),
                retry_policy=RetryPolicy(maximum_attempts=2)
            ),
            spec=Schedule.Spec(
                cron_expressions=[schedule_config.get("cron", "0 */6 * * *")],  # Every 6 hours by default
                timezone=schedule_config.get("timezone", "UTC"),
                jitter=timedelta(minutes=schedule_config.get("jitter_minutes", 10))
            ),
            policy=Schedule.Policy(
                overlap=Schedule.OverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=False  # Continue running even if one batch fails
            )
        )
        
        schedule_handle = await self.client.create_schedule(
            schedule_id,
            schedule,
            note="Multi-tenant sync orchestrator",
            search_attributes={"schedule_type": "multi_tenant_sync"}
        )
        
        self.active_schedules[schedule_id] = schedule_handle
        
        print(f"Created multi-tenant sync schedule: {schedule_id}")
        return schedule_handle
    
    async def create_health_monitor_schedule(
        self,
        monitor_config: Dict[str, Any]
    ) -> ScheduleHandle:
        """
        Create a schedule for sync health monitoring.
        
        Args:
            monitor_config: Monitoring configuration
            
        Returns:
            Handle to the created schedule
        """
        
        schedule_id = "sync-health-monitor"
        
        # Create the schedule for health monitoring
        schedule = Schedule(
            action=Schedule.Action(
                workflow=SyncHealthMonitorWorkflow.run,
                args=[monitor_config],
                id=f"health-monitor-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                task_queue="media-planner-sync-queue",
                execution_timeout=timedelta(hours=24),  # Long-running monitor
                retry_policy=RetryPolicy(maximum_attempts=1)  # Don't retry, just restart
            ),
            spec=Schedule.Spec(
                cron_expressions=["0 0 * * *"],  # Start daily at midnight
                timezone=monitor_config.get("timezone", "UTC")
            ),
            policy=Schedule.Policy(
                overlap=Schedule.OverlapPolicy.TERMINATE_OTHER,  # Terminate previous and start new
                catchup_window=timedelta(hours=1)
            )
        )
        
        schedule_handle = await self.client.create_schedule(
            schedule_id,
            schedule,
            note="Sync health monitoring service",
            search_attributes={"schedule_type": "health_monitor"}
        )
        
        self.active_schedules[schedule_id] = schedule_handle
        
        print(f"Created health monitor schedule: {schedule_id}")
        return schedule_handle
    
    async def update_tenant_sync_schedule(
        self,
        tenant_id: str,
        new_config: Dict[str, Any]
    ) -> bool:
        """
        Update an existing tenant sync schedule with new configuration.
        
        Args:
            tenant_id: Tenant identifier
            new_config: New scheduling configuration
            
        Returns:
            True if update was successful
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        if schedule_id not in self.active_schedules:
            print(f"No active schedule found for tenant {tenant_id}")
            return False
        
        schedule_handle = self.active_schedules[schedule_id]
        
        try:
            # Update the schedule spec
            await schedule_handle.update(
                lambda schedule: schedule.with_spec(
                    Schedule.Spec(
                        cron_expressions=[new_config.get("cron", "0 */1 * * *")],
                        timezone=new_config.get("timezone", "UTC"),
                        jitter=timedelta(minutes=new_config.get("jitter_minutes", 5))
                    )
                )
            )
            
            print(f"Updated sync schedule for tenant {tenant_id}")
            return True
            
        except Exception as e:
            print(f"Failed to update schedule for tenant {tenant_id}: {str(e)}")
            return False
    
    async def pause_tenant_sync_schedule(self, tenant_id: str, note: str = "") -> bool:
        """
        Pause a tenant's sync schedule.
        
        Args:
            tenant_id: Tenant identifier
            note: Optional note about why it was paused
            
        Returns:
            True if pause was successful
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        if schedule_id not in self.active_schedules:
            print(f"No active schedule found for tenant {tenant_id}")
            return False
        
        schedule_handle = self.active_schedules[schedule_id]
        
        try:
            await schedule_handle.pause(note)
            print(f"Paused sync schedule for tenant {tenant_id}: {note}")
            return True
            
        except Exception as e:
            print(f"Failed to pause schedule for tenant {tenant_id}: {str(e)}")
            return False
    
    async def resume_tenant_sync_schedule(self, tenant_id: str, note: str = "") -> bool:
        """
        Resume a paused tenant sync schedule.
        
        Args:
            tenant_id: Tenant identifier
            note: Optional note about why it was resumed
            
        Returns:
            True if resume was successful
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        if schedule_id not in self.active_schedules:
            print(f"No active schedule found for tenant {tenant_id}")
            return False
        
        schedule_handle = self.active_schedules[schedule_id]
        
        try:
            await schedule_handle.unpause(note)
            print(f"Resumed sync schedule for tenant {tenant_id}: {note}")
            return True
            
        except Exception as e:
            print(f"Failed to resume schedule for tenant {tenant_id}: {str(e)}")
            return False
    
    async def delete_tenant_sync_schedule(self, tenant_id: str) -> bool:
        """
        Delete a tenant's sync schedule.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if deletion was successful
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        if schedule_id not in self.active_schedules:
            print(f"No active schedule found for tenant {tenant_id}")
            return False
        
        schedule_handle = self.active_schedules[schedule_id]
        
        try:
            await schedule_handle.delete()
            del self.active_schedules[schedule_id]
            print(f"Deleted sync schedule for tenant {tenant_id}")
            return True
            
        except Exception as e:
            print(f"Failed to delete schedule for tenant {tenant_id}: {str(e)}")
            return False
    
    async def list_active_schedules(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active sync schedules with their current status.
        
        Returns:
            Dictionary of schedule information
        """
        
        schedule_info = {}
        
        for schedule_id, schedule_handle in self.active_schedules.items():
            try:
                description = await schedule_handle.describe()
                
                schedule_info[schedule_id] = {
                    "id": schedule_id,
                    "state": description.schedule.state,
                    "next_action_times": description.info.next_action_times,
                    "recent_actions": [
                        {
                            "scheduled_time": action.scheduled_time,
                            "actual_time": action.actual_time,
                            "result": action.result
                        }
                        for action in description.info.recent_actions[-5:]  # Last 5 actions
                    ],
                    "note": description.schedule.note
                }
                
            except Exception as e:
                schedule_info[schedule_id] = {
                    "id": schedule_id,
                    "error": f"Failed to get info: {str(e)}"
                }
        
        return schedule_info
    
    async def trigger_immediate_sync(
        self,
        tenant_id: str,
        overlap_policy: str = "skip"
    ) -> bool:
        """
        Trigger an immediate sync for a tenant, bypassing the schedule.
        
        Args:
            tenant_id: Tenant identifier
            overlap_policy: How to handle if sync is already running ("skip", "allow", "terminate")
            
        Returns:
            True if trigger was successful
        """
        
        schedule_id = f"tenant-sync-{tenant_id}"
        
        if schedule_id not in self.active_schedules:
            print(f"No active schedule found for tenant {tenant_id}")
            return False
        
        schedule_handle = self.active_schedules[schedule_id]
        
        try:
            # Trigger the schedule immediately
            await schedule_handle.trigger(
                overlap=Schedule.OverlapPolicy.SKIP if overlap_policy == "skip" 
                       else Schedule.OverlapPolicy.ALLOW if overlap_policy == "allow"
                       else Schedule.OverlapPolicy.TERMINATE_OTHER
            )
            
            print(f"Triggered immediate sync for tenant {tenant_id}")
            return True
            
        except Exception as e:
            print(f"Failed to trigger sync for tenant {tenant_id}: {str(e)}")
            return False


# Convenience functions for common scheduling patterns

async def setup_default_sync_schedules(
    client: Client,
    tenants: List[Dict[str, Any]]
) -> SyncScheduler:
    """
    Set up default sync schedules for a list of tenants.
    
    Args:
        client: Temporal client
        tenants: List of tenant configurations
        
    Returns:
        Configured SyncScheduler instance
    """
    
    scheduler = SyncScheduler(client)
    
    # Create individual tenant schedules
    for tenant_config in tenants:
        tenant_id = tenant_config["tenant_id"]
        
        # Default scheduling configuration
        schedule_config = {
            "cron": tenant_config.get("sync_cron", "0 */2 * * *"),  # Every 2 hours
            "timezone": tenant_config.get("timezone", "UTC"),
            "jitter_minutes": 5,
            "catchup_window_minutes": 60,
            "pause_on_failure": True
        }
        
        await scheduler.create_tenant_sync_schedule(
            tenant_id, tenant_config, schedule_config
        )
    
    # Create multi-tenant orchestrator (runs less frequently)
    orchestrator_schedule_config = {
        "cron": "0 */6 * * *",  # Every 6 hours
        "timezone": "UTC",
        "max_concurrent": 3,
        "jitter_minutes": 10
    }
    
    await scheduler.create_multi_tenant_sync_schedule(
        tenants, orchestrator_schedule_config
    )
    
    # Create health monitor
    monitor_config = {
        "monitoring_interval": 15,  # Check every 15 minutes
        "alert_thresholds": {
            "error_rate": 0.1,  # 10% error rate threshold
            "avg_duration_minutes": 30  # Alert if syncs take longer than 30 minutes
        },
        "notification_settings": {
            "health_alerts": ["admin@company.com"]
        },
        "timezone": "UTC"
    }
    
    await scheduler.create_health_monitor_schedule(monitor_config)
    
    print(f"Set up sync schedules for {len(tenants)} tenants")
    return scheduler


# Schedule configuration examples

SYNC_SCHEDULE_PRESETS = {
    "frequent": {
        "cron": "0 */1 * * *",  # Every hour
        "description": "Frequent sync for high-activity tenants"
    },
    "normal": {
        "cron": "0 */2 * * *",  # Every 2 hours
        "description": "Normal sync frequency"
    },
    "light": {
        "cron": "0 */4 * * *",  # Every 4 hours
        "description": "Light sync for low-activity tenants"
    },
    "daily": {
        "cron": "0 6 * * *",   # Daily at 6 AM
        "description": "Daily sync for archival tenants"
    },
    "business_hours": {
        "cron": "0 9-17/2 * * MON-FRI",  # Every 2 hours during business hours, weekdays only
        "description": "Business hours only sync"
    }
} 