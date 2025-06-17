"""
Temporal activities for media planning platform integrations.

This module contains all activity definitions for:
- Google Ads integration
- Meta Ads integration  
- Google Drive integration
- Common utilities and error handling
"""

from .google_ads_activities import (
    authenticate_google_ads,
    fetch_google_ads_campaigns,
    fetch_google_ads_keywords,
    fetch_google_ads_reports,
    transform_google_ads_data,
)

from .meta_ads_activities import (
    authenticate_meta_ads,
    fetch_meta_ads_campaigns,
    fetch_meta_ads_insights,
    fetch_meta_ads_audiences,
    transform_meta_ads_data,
)

from .google_drive_activities import (
    authenticate_google_drive,
    fetch_google_drive_files,
    download_google_drive_file,
    parse_google_drive_content,
    transform_google_drive_data,
)

from .common_activities import (
    validate_data_integrity,
    store_integration_data,
    send_notification,
    log_integration_event,
    handle_integration_error,
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
]
