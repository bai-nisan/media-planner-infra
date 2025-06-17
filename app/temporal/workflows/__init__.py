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
    GoogleAdsIntegrationWorkflow,
    GoogleAdsCampaignSyncWorkflow,
    GoogleAdsReportingWorkflow,
)

from .meta_ads_workflows import (
    MetaAdsIntegrationWorkflow,
    MetaAdsCampaignSyncWorkflow,
    MetaAdsInsightsWorkflow,
)

from .google_drive_workflows import (
    GoogleDriveIntegrationWorkflow,
    GoogleDriveFileSyncWorkflow,
    GoogleDriveContentParsingWorkflow,
)

from .integration_orchestrator import (
    PlatformIntegrationOrchestratorWorkflow,
    MultiPlatformDataSyncWorkflow,
    IntegrationHealthCheckWorkflow,
)

from .sync_workflows import (
    ScheduledSyncWorkflow,
    MultiTenantSyncOrchestratorWorkflow,
    ConflictResolutionWorkflow,
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
