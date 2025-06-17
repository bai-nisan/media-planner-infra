"""
Google Drive integration workflows for the media planning platform.

These workflows orchestrate Google Drive file synchronization, content parsing,
and data import activities with proper error handling and retry mechanisms.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
from app.temporal.activities.google_drive_activities import (
    authenticate_google_drive,
    fetch_google_drive_files,
    download_google_drive_file,
    parse_google_drive_content,
    transform_google_drive_data,
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
class GoogleDriveIntegrationWorkflow:
    """Main Google Drive integration workflow for complete file synchronization."""
    
    @workflow.run
    async def run(
        self,
        credentials: Dict[str, Any],
        tenant_id: str,
        sync_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the complete Google Drive integration process."""
        integration_id = f"google_drive_{tenant_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Step 1: Authenticate
            auth_data = await workflow.execute_activity(
                authenticate_google_drive,
                credentials,
                tenant_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=3,
                )
            )
            
            # Step 2: Fetch files
            files = await workflow.execute_activity(
                fetch_google_drive_files,
                auth_data,
                sync_config.get("folder_id"),
                sync_config.get("file_types", ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]),
                sync_config.get("modified_since"),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=5,
                )
            )
            
            # Step 3: Download and parse files
            parsed_files = []
            for file_info in files:
                try:
                    # Download file
                    file_content = await workflow.execute_activity(
                        download_google_drive_file,
                        auth_data,
                        file_info["file_id"],
                        sync_config.get("export_format"),
                        start_to_close_timeout=timedelta(minutes=10)
                    )
                    
                    # Parse content
                    parsed_content = await workflow.execute_activity(
                        parse_google_drive_content,
                        file_content,
                        sync_config.get("parsing_config", {}),
                        start_to_close_timeout=timedelta(minutes=15)
                    )
                    
                    parsed_files.append({
                        "file_info": file_info,
                        "parsed_content": parsed_content
                    })
                    
                except Exception as e:
                    workflow.logger.warning(f"Failed to process file {file_info['file_id']}: {str(e)}")
            
            # Step 4: Transform data
            raw_data = {
                "files": parsed_files,
                "tenant_id": tenant_id
            }
            
            transformed_data = await workflow.execute_activity(
                transform_google_drive_data,
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
                "tenant_id": tenant_id,
                "data_summary": {
                    "files_found": len(files),
                    "files_processed": len(parsed_files),
                    "validation_status": validation_result["is_valid"],
                    "storage_status": storage_result["success"] if storage_result else False
                },
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Google Drive integration failed: {str(e)}")
            return {
                "integration_id": integration_id,
                "status": "error",
                "tenant_id": tenant_id,
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class GoogleDriveFileSyncWorkflow:
    """Focused workflow for syncing Google Drive files only."""
    
    @workflow.run
    async def run(
        self,
        auth_data: Dict[str, Any],
        tenant_id: str,
        folder_id: Optional[str] = None,
        file_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Sync Google Drive files."""
        sync_id = f"drive_file_sync_{tenant_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            files = await workflow.execute_activity(
                fetch_google_drive_files,
                auth_data,
                folder_id,
                file_types,
                None,  # No modified_since filter
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            # Store file metadata
            file_metadata = {
                "source": "google_drive",
                "files": files,
                "tenant_id": tenant_id
            }
            
            storage_result = await workflow.execute_activity(
                store_integration_data,
                file_metadata,
                {"table": "drive_files", "upsert": True},
                tenant_id,
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            return {
                "sync_id": sync_id,
                "status": "success",
                "files_synced": len(files),
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Drive file sync failed: {str(e)}")
            return {
                "sync_id": sync_id,
                "status": "error",
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            }


@workflow.defn
class GoogleDriveContentParsingWorkflow:
    """Dedicated workflow for parsing Google Drive file content."""
    
    @workflow.run
    async def run(
        self,
        auth_data: Dict[str, Any],
        file_id: str,
        parsing_config: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Parse specific Google Drive file content."""
        parse_id = f"drive_parse_{file_id}_{workflow.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Download file
            file_content = await workflow.execute_activity(
                download_google_drive_file,
                auth_data,
                file_id,
                parsing_config.get("export_format"),
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            # Parse content
            parsed_content = await workflow.execute_activity(
                parse_google_drive_content,
                file_content,
                parsing_config,
                start_to_close_timeout=timedelta(minutes=15)
            )
            
            # Transform and store
            transformed_data = await workflow.execute_activity(
                transform_google_drive_data,
                {"files": [{"parsed_content": parsed_content}]},
                parsing_config.get("transformation_config", {}),
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            storage_result = await workflow.execute_activity(
                store_integration_data,
                transformed_data,
                {"table": "drive_content", "file_id": file_id},
                tenant_id,
                start_to_close_timeout=timedelta(minutes=10)
            )
            
            return {
                "parse_id": parse_id,
                "status": "success",
                "file_id": file_id,
                "parsed_content": parsed_content,
                "storage_result": storage_result,
                "completed_at": workflow.now().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Drive content parsing failed: {str(e)}")
            return {
                "parse_id": parse_id,
                "status": "error",
                "file_id": file_id,
                "error": str(e),
                "failed_at": workflow.now().isoformat()
            } 