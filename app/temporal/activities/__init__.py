"""
Temporal activities for media planning platform integrations.

This module contains all activity definitions for:
- Google Ads integration
- Meta Ads integration
- Google Drive integration
- Common utilities and error handling
- Sync-specific operations for scheduled synchronization
"""

from .common_activities import (  # Sync-specific activities
    handle_integration_error,
    load_sync_checkpoint,
    log_integration_event,
    log_sync_event,
    resolve_data_conflicts,
    send_notification,
    store_integration_data,
    store_sync_checkpoint,
    validate_data_integrity,
    validate_sync_data,
)
from .google_ads_activities import (
    authenticate_google_ads,
    fetch_google_ads_campaigns,
    fetch_google_ads_keywords,
    fetch_google_ads_reports,
    transform_google_ads_data,
)
from .google_drive_activities import (
    authenticate_google_drive,
    download_google_drive_file,
    fetch_google_drive_files,
    parse_google_drive_content,
    transform_google_drive_data,
)
from .meta_ads_activities import (
    authenticate_meta_ads,
    fetch_meta_ads_audiences,
    fetch_meta_ads_campaigns,
    fetch_meta_ads_insights,
    transform_meta_ads_data,
)

__all__ = [
    # Google Ads activities
    "authenticate_google_ads",
    "fetch_google_ads_campaigns",
    "fetch_google_ads_keywords",
    "fetch_google_ads_reports",
    "transform_google_ads_data",
    # Meta Ads activities
    "authenticate_meta_ads",
    "fetch_meta_ads_campaigns",
    "fetch_meta_ads_insights",
    "fetch_meta_ads_audiences",
    "transform_meta_ads_data",
    # Google Drive activities
    "authenticate_google_drive",
    "fetch_google_drive_files",
    "download_google_drive_file",
    "parse_google_drive_content",
    "transform_google_drive_data",
    # Common activities
    "validate_data_integrity",
    "store_integration_data",
    "send_notification",
    "log_integration_event",
    "handle_integration_error",
    # Sync-specific activities
    "validate_sync_data",
    "resolve_data_conflicts",
    "log_sync_event",
    "store_sync_checkpoint",
    "load_sync_checkpoint",
]
