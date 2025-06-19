"""
Temporal workflows for media planning platform integrations.

This module contains all workflow definitions for:
- Google Ads integration
- Meta Ads integration
- Google Drive integration
- Combined platform integrations
- Scheduled synchronization workflows
"""

from .google_ads_workflows import (
    GoogleAdsCampaignSyncWorkflow,
    GoogleAdsIntegrationWorkflow,
    GoogleAdsReportingWorkflow,
)
from .google_drive_workflows import (
    GoogleDriveContentParsingWorkflow,
    GoogleDriveFileSyncWorkflow,
    GoogleDriveIntegrationWorkflow,
)
from .integration_orchestrator import (
    IntegrationHealthCheckWorkflow,
    MultiPlatformDataSyncWorkflow,
    PlatformIntegrationOrchestratorWorkflow,
)
from .meta_ads_workflows import (
    MetaAdsCampaignSyncWorkflow,
    MetaAdsInsightsWorkflow,
    MetaAdsIntegrationWorkflow,
)
from .sync_workflows import (
    ConflictResolutionWorkflow,
    MultiTenantSyncOrchestratorWorkflow,
    ScheduledSyncWorkflow,
    SyncHealthMonitorWorkflow,
)

__all__ = [
    # Google Ads workflows
    "GoogleAdsIntegrationWorkflow",
    "GoogleAdsCampaignSyncWorkflow",
    "GoogleAdsReportingWorkflow",
    # Meta Ads workflows
    "MetaAdsIntegrationWorkflow",
    "MetaAdsCampaignSyncWorkflow",
    "MetaAdsInsightsWorkflow",
    # Google Drive workflows
    "GoogleDriveIntegrationWorkflow",
    "GoogleDriveFileSyncWorkflow",
    "GoogleDriveContentParsingWorkflow",
    # Orchestrator workflows
    "PlatformIntegrationOrchestratorWorkflow",
    "MultiPlatformDataSyncWorkflow",
    "IntegrationHealthCheckWorkflow",
    # Sync workflows
    "ScheduledSyncWorkflow",
    "MultiTenantSyncOrchestratorWorkflow",
    "ConflictResolutionWorkflow",
    "SyncHealthMonitorWorkflow",
]
