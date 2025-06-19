"""
Example: Media Planning Platform Sync Workflows

This script demonstrates how to use the sync workflows and schedulers
for periodic data synchronization across Google Ads, Meta Ads, and Google Drive.
"""

import asyncio
from datetime import datetime, timedelta

from temporalio.client import Client

from ..schedulers import (
    SYNC_SCHEDULE_PRESETS,
    SyncScheduler,
    setup_default_sync_schedules,
)
from ..workflows.sync_workflows import (
    ConflictResolutionWorkflow,
    MultiTenantSyncOrchestratorWorkflow,
    ScheduledSyncWorkflow,
)


async def main():
    """
    Main example function demonstrating sync workflow usage.
    """

    # Connect to Temporal cluster
    client = await Client.connect("localhost:7233")

    print("🚀 Starting Sync Workflows Example")
    print("=" * 50)

    # Example tenant configurations
    tenants = [
        {
            "tenant_id": "acme-corp",
            "platforms": ["google_ads", "meta_ads", "google_drive"],
            "sync_cron": "0 */1 * * *",  # Every hour
            "timezone": "America/New_York",
            "conflict_resolution": "latest_wins",
            "notification_settings": {
                "success": ["admin@acme-corp.com"],
                "error": ["alerts@acme-corp.com"],
            },
            "google_ads_config": {
                "customer_id": "123-456-7890",
                "include_keywords": True,
                "include_reports": True,
            },
            "meta_ads_config": {
                "ad_account_id": "act_123456789",
                "include_audiences": True,
                "insights_days": 7,
            },
            "google_drive_config": {
                "folder_ids": ["1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"],
                "file_types": [".xlsx", ".csv", ".json"],
            },
        },
        {
            "tenant_id": "globex-ltd",
            "platforms": ["google_ads", "meta_ads"],
            "sync_cron": "0 */2 * * *",  # Every 2 hours
            "timezone": "Europe/London",
            "conflict_resolution": "source_priority",
            "notification_settings": {
                "success": ["ops@globex-ltd.com"],
                "error": ["emergency@globex-ltd.com"],
            },
        },
        {
            "tenant_id": "startup-inc",
            "platforms": ["meta_ads", "google_drive"],
            "sync_cron": "0 */4 * * *",  # Every 4 hours
            "timezone": "America/Los_Angeles",
            "conflict_resolution": "manual_review",
            "notification_settings": {
                "success": ["team@startup-inc.com"],
                "error": ["alerts@startup-inc.com"],
            },
        },
    ]

    # 1. Demonstrate individual tenant sync workflow
    print("\n📊 1. Individual Tenant Sync Example")
    print("-" * 40)

    tenant_config = tenants[0]  # ACME Corp

    result = await client.execute_workflow(
        ScheduledSyncWorkflow.run,
        tenant_config,
        id=f"demo-sync-{tenant_config['tenant_id']}-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_queue="media-planner-sync-queue",
        execution_timeout=timedelta(minutes=30),
    )

    print(f"✅ Individual sync completed for {tenant_config['tenant_id']}")
    print(f"   Status: {result['status']}")
    print(f"   Platforms synced: {result['platforms_synced']}")
    print(f"   Sync type: {result['sync_type']}")

    # 2. Demonstrate multi-tenant orchestration
    print("\n🏢 2. Multi-Tenant Orchestration Example")
    print("-" * 40)

    orchestrator_config = {
        "tenants": tenants,
        "max_concurrent_syncs": 2,
        "priority_levels": {
            "acme-corp": "high",
            "globex-ltd": "medium",
            "startup-inc": "low",
        },
        "resource_limits": {"max_memory_gb": 4, "max_cpu_cores": 2},
    }

    orchestrator_result = await client.execute_workflow(
        MultiTenantSyncOrchestratorWorkflow.run,
        orchestrator_config,
        id=f"demo-orchestrator-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_queue="media-planner-sync-queue",
        execution_timeout=timedelta(hours=1),
    )

    print(f"✅ Multi-tenant orchestration completed")
    print(f"   Total tenants: {orchestrator_result['total_tenants']}")
    print(f"   Successful syncs: {orchestrator_result['successful_syncs']}")
    print(f"   Failed syncs: {orchestrator_result['failed_syncs']}")

    # 3. Demonstrate conflict resolution
    print("\n⚠️  3. Conflict Resolution Example")
    print("-" * 40)

    # Simulate conflicts
    mock_conflicts = [
        {
            "conflict_id": "conflict_001",
            "type": "campaign_name_mismatch",
            "platforms": ["google_ads", "meta_ads"],
            "description": "Campaign 'Summer Sale' has different names across platforms",
            "severity": "medium",
            "tenant_id": "acme-corp",
            "detected_at": datetime.utcnow().isoformat(),
        },
        {
            "conflict_id": "conflict_002",
            "type": "budget_discrepancy",
            "platforms": ["google_ads", "meta_ads"],
            "description": "Total budget allocation exceeds 100%",
            "severity": "high",
            "tenant_id": "acme-corp",
            "detected_at": datetime.utcnow().isoformat(),
        },
    ]

    conflict_config = {
        "tenant_id": "acme-corp",
        "conflicts": mock_conflicts,
        "resolution_strategy": "latest_wins",
        "escalation_rules": {"recipients": ["admin@acme-corp.com"]},
    }

    conflict_result = await client.execute_workflow(
        ConflictResolutionWorkflow.run,
        conflict_config,
        id=f"demo-conflicts-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_queue="media-planner-sync-queue",
        execution_timeout=timedelta(minutes=15),
    )

    print(f"✅ Conflict resolution completed")
    print(f"   Total conflicts: {conflict_result['total_conflicts']}")
    print(f"   Resolved conflicts: {len(conflict_result['resolved_conflicts'])}")
    print(f"   Escalated conflicts: {len(conflict_result['escalated_conflicts'])}")

    # 4. Demonstrate scheduling setup
    print("\n⏰ 4. Scheduling Setup Example")
    print("-" * 40)

    # Set up default schedules for all tenants
    scheduler = await setup_default_sync_schedules(client, tenants)

    print(f"✅ Created schedules for {len(tenants)} tenants")

    # List active schedules
    schedule_info = await scheduler.list_active_schedules()
    print(f"📋 Active schedules:")
    for schedule_id, info in schedule_info.items():
        if "error" not in info:
            print(f"   • {schedule_id}: {info.get('state', 'unknown')}")
        else:
            print(f"   • {schedule_id}: ERROR - {info['error']}")

    # 5. Demonstrate schedule management
    print("\n🔧 5. Schedule Management Example")
    print("-" * 40)

    # Update a tenant's schedule
    print("Updating ACME Corp sync frequency...")
    success = await scheduler.update_tenant_sync_schedule(
        "acme-corp",
        {"cron": "0 */30 * * *", "timezone": "America/New_York"},  # Every 30 minutes
    )
    print(f"✅ Schedule update: {'successful' if success else 'failed'}")

    # Pause a tenant's schedule
    print("Pausing Startup Inc sync for maintenance...")
    success = await scheduler.pause_tenant_sync_schedule(
        "startup-inc", "Temporary pause for system maintenance"
    )
    print(f"✅ Schedule pause: {'successful' if success else 'failed'}")

    # Trigger immediate sync
    print("Triggering immediate sync for Globex Ltd...")
    success = await scheduler.trigger_immediate_sync("globex-ltd")
    print(f"✅ Immediate sync trigger: {'successful' if success else 'failed'}")

    # Resume paused schedule
    print("Resuming Startup Inc sync...")
    success = await scheduler.resume_tenant_sync_schedule(
        "startup-inc", "Maintenance completed"
    )
    print(f"✅ Schedule resume: {'successful' if success else 'failed'}")

    # 6. Show scheduling presets
    print("\n📋 6. Available Scheduling Presets")
    print("-" * 40)

    for preset_name, preset_config in SYNC_SCHEDULE_PRESETS.items():
        print(
            f"   • {preset_name}: {preset_config['cron']} - {preset_config['description']}"
        )

    print("\n🎉 Sync Workflows Example Completed!")
    print("=" * 50)

    # Clean up schedules (optional - remove in production)
    print("\n🧹 Cleaning up demo schedules...")
    for tenant in tenants:
        await scheduler.delete_tenant_sync_schedule(tenant["tenant_id"])

    print("✅ Demo cleanup completed")


async def run_custom_sync_example():
    """
    Example of running a custom sync with specific configuration.
    """

    client = await Client.connect("localhost:7233")

    print("\n🎯 Custom Sync Configuration Example")
    print("-" * 40)

    # Custom sync configuration for a specific use case
    custom_sync_config = {
        "tenant_id": "enterprise-client",
        "platforms": ["google_ads", "meta_ads", "google_drive"],
        "sync_interval": 30,  # 30 minutes
        "full_sync_interval": 6,  # 6 hours for full sync
        "conflict_resolution": "source_priority",
        "validation_rules": {
            "google_ads_required_fields": ["campaign_id", "campaign_name", "status"],
            "meta_ads_required_fields": ["campaign_id", "campaign_name", "objective"],
            "google_drive_required_fields": ["file_id", "file_name", "modified_time"],
        },
        "notification_settings": {
            "success": ["success@enterprise-client.com"],
            "error": ["alerts@enterprise-client.com", "ops@enterprise-client.com"],
        },
        "google_ads_config": {
            "customer_id": "987-654-3210",
            "include_keywords": True,
            "include_reports": True,
            "report_days": 30,
            "performance_metrics": ["impressions", "clicks", "cost", "conversions"],
        },
        "meta_ads_config": {
            "ad_account_id": "act_987654321",
            "include_audiences": True,
            "insights_days": 30,
            "breakdown_dimensions": ["age", "gender", "placement"],
        },
        "google_drive_config": {
            "folder_ids": [
                "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "1ABcDEFGhijklmnOPqrstUVwxyz0123456789abcDEF",
            ],
            "file_types": [".xlsx", ".csv", ".json", ".pdf"],
            "parse_content": True,
            "extract_tables": True,
        },
    }

    # Execute the custom sync
    result = await client.execute_workflow(
        ScheduledSyncWorkflow.run,
        custom_sync_config,
        id=f"custom-sync-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_queue="media-planner-sync-queue",
        execution_timeout=timedelta(hours=1),
    )

    print(f"✅ Custom sync completed")
    print(f"   Tenant: {result['tenant_id']}")
    print(f"   Status: {result['status']}")
    print(f"   Sync type: {result['sync_type']}")
    print(f"   Platforms: {', '.join(result['platforms_synced'])}")
    print(f"   Completed at: {result['completed_at']}")

    # Show detailed results
    if "sync_results" in result:
        print(f"\n📊 Detailed Results:")
        for platform, platform_result in result["sync_results"].items():
            status = platform_result.get("status", "unknown")
            record_count = platform_result.get("record_count", 0)
            print(f"   • {platform}: {status} ({record_count} records)")


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())

    # Uncomment to run custom sync example
    # asyncio.run(run_custom_sync_example())
