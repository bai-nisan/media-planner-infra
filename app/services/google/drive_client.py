"""
Google Drive API Client

Provides methods for discovering and managing campaign files in Google Drive.
Follows FastAPI dependency injection patterns and integrates with auth manager.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.core.config import Settings

from .auth import GoogleAuthManager

logger = logging.getLogger(__name__)


class DriveFile(BaseModel):
    """Pydantic model for Google Drive file."""

    id: str
    name: str
    mime_type: str
    size: Optional[int] = None
    created_time: datetime
    modified_time: datetime
    web_view_link: str
    parents: List[str] = []
    shared: bool = False


class DriveFolder(BaseModel):
    """Pydantic model for Google Drive folder."""

    id: str
    name: str
    created_time: datetime
    modified_time: datetime
    web_view_link: str
    parents: List[str] = []
    file_count: int = 0


class GoogleDriveClient:
    """
    Google Drive API client for media planning file operations.

    Provides methods for:
    - Discovering campaign files and folders
    - Reading file metadata
    - Searching for files by criteria
    - Managing permissions (future)

    Supports context manager usage for proper resource cleanup.
    """

    def __init__(self, auth_manager: GoogleAuthManager, settings: Settings):
        """Initialize the Drive client."""
        self.auth_manager = auth_manager
        self.settings = settings
        self._service = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def close(self):
        """Close the service and cleanup resources."""
        if self._service:
            try:
                self._service.close()
            except Exception as e:
                logger.warning(f"Error closing Drive service: {e}")
            finally:
                self._service = None

    @property
    def service(self):
        """Get authenticated Drive service."""
        if not self._service:
            credentials = self.auth_manager.get_valid_credentials()
            if not credentials:
                raise ValueError("No valid Google credentials available")

            self._service = build(
                "drive",
                "v3",
                credentials=credentials,
                cache_discovery=False,  # Recommended for production
            )
        return self._service

    @contextmanager
    def _handle_api_errors(self, operation: str):
        """Context manager for consistent error handling."""
        try:
            yield
        except HttpError as e:
            logger.error(f"Drive API error during {operation}: {e}")
            if e.resp.status in [401, 403]:
                # Clear invalid credentials
                self.auth_manager.credentials = None
            raise
        except Exception as e:
            logger.error(f"Unexpected error during {operation}: {e}")
            raise

    def list_files(
        self,
        folder_id: Optional[str] = None,
        file_types: Optional[List[str]] = None,
        limit: int = 100,
        include_shared: bool = True,
    ) -> List[DriveFile]:
        """
        List files in Drive with optional filtering.

        Args:
            folder_id: Specific folder to search in
            file_types: MIME types to filter by
            limit: Maximum number of files to return
            include_shared: Whether to include shared files

        Returns:
            List of Drive files
        """
        with self._handle_api_errors("list_files"):
            # Build query
            query_parts = []

            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            if file_types:
                mime_queries = [f"mimeType='{mime}'" for mime in file_types]
                query_parts.append(f"({' or '.join(mime_queries)})")

            if not include_shared:
                query_parts.append("sharedWithMe=false")

            # Don't include trashed files
            query_parts.append("trashed=false")

            query = " and ".join(query_parts) if query_parts else "trashed=false"

            # Execute request
            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=min(limit, 1000),  # Drive API max is 1000
                    fields="nextPageToken, files(id, name, mimeType, size, "
                    "createdTime, modifiedTime, webViewLink, parents, shared)",
                )
                .execute()
            )

            files = results.get("files", [])

            # Convert to Pydantic models
            drive_files = []
            for file_data in files:
                try:
                    drive_file = DriveFile(
                        id=file_data["id"],
                        name=file_data["name"],
                        mime_type=file_data["mimeType"],
                        size=file_data.get("size"),
                        created_time=datetime.fromisoformat(
                            file_data["createdTime"].replace("Z", "+00:00")
                        ),
                        modified_time=datetime.fromisoformat(
                            file_data["modifiedTime"].replace("Z", "+00:00")
                        ),
                        web_view_link=file_data["webViewLink"],
                        parents=file_data.get("parents", []),
                        shared=file_data.get("shared", False),
                    )
                    drive_files.append(drive_file)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse file {file_data.get('name', 'unknown')}: {e}"
                    )
                    continue

            logger.info(f"Retrieved {len(drive_files)} files from Drive")
            return drive_files

    def search_files(self, query: str, limit: int = 50) -> List[DriveFile]:
        """
        Search for files by name or content.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching Drive files
        """
        try:
            # Escape query for Drive API
            escaped_query = query.replace("'", "\\'")
            search_query = f"name contains '{escaped_query}' and trashed=false"

            results = (
                self.service.files()
                .list(
                    q=search_query,
                    pageSize=min(limit, 1000),
                    fields="files(id, name, mimeType, size, createdTime, "
                    "modifiedTime, webViewLink, parents, shared)",
                )
                .execute()
            )

            files = results.get("files", [])

            # Convert to Pydantic models
            drive_files = []
            for file_data in files:
                try:
                    drive_file = DriveFile(
                        id=file_data["id"],
                        name=file_data["name"],
                        mime_type=file_data["mimeType"],
                        size=file_data.get("size"),
                        created_time=datetime.fromisoformat(
                            file_data["createdTime"].replace("Z", "+00:00")
                        ),
                        modified_time=datetime.fromisoformat(
                            file_data["modifiedTime"].replace("Z", "+00:00")
                        ),
                        web_view_link=file_data["webViewLink"],
                        parents=file_data.get("parents", []),
                        shared=file_data.get("shared", False),
                    )
                    drive_files.append(drive_file)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse search result {file_data.get('name', 'unknown')}: {e}"
                    )
                    continue

            logger.info(f"Found {len(drive_files)} files matching '{query}'")
            return drive_files

        except HttpError as e:
            logger.error(f"Drive API search error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching files: {e}")
            raise

    def get_file_metadata(self, file_id: str) -> Optional[DriveFile]:
        """
        Get detailed metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            DriveFile object or None if not found
        """
        try:
            file_data = (
                self.service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, size, createdTime, "
                    "modifiedTime, webViewLink, parents, shared",
                )
                .execute()
            )

            return DriveFile(
                id=file_data["id"],
                name=file_data["name"],
                mime_type=file_data["mimeType"],
                size=file_data.get("size"),
                created_time=datetime.fromisoformat(
                    file_data["createdTime"].replace("Z", "+00:00")
                ),
                modified_time=datetime.fromisoformat(
                    file_data["modifiedTime"].replace("Z", "+00:00")
                ),
                web_view_link=file_data["webViewLink"],
                parents=file_data.get("parents", []),
                shared=file_data.get("shared", False),
            )

        except HttpError as e:
            if e.resp.status == 404:
                logger.info(f"File {file_id} not found")
                return None
            logger.error(f"Drive API error getting file metadata: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting file metadata: {e}")
            raise

    def list_folders(
        self, parent_folder_id: Optional[str] = None, limit: int = 100
    ) -> List[DriveFolder]:
        """
        List folders in Drive.

        Args:
            parent_folder_id: Parent folder to search in
            limit: Maximum number of folders to return

        Returns:
            List of Drive folders
        """
        try:
            # Build query for folders
            query_parts = [
                "mimeType='application/vnd.google-apps.folder'",
                "trashed=false",
            ]

            if parent_folder_id:
                query_parts.append(f"'{parent_folder_id}' in parents")

            query = " and ".join(query_parts)

            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=min(limit, 1000),
                    fields="files(id, name, createdTime, modifiedTime, webViewLink, parents)",
                )
                .execute()
            )

            folders = results.get("files", [])

            # Convert to Pydantic models and get file counts
            drive_folders = []
            for folder_data in folders:
                try:
                    # Get file count for this folder
                    file_count = self._get_folder_file_count(folder_data["id"])

                    drive_folder = DriveFolder(
                        id=folder_data["id"],
                        name=folder_data["name"],
                        created_time=datetime.fromisoformat(
                            folder_data["createdTime"].replace("Z", "+00:00")
                        ),
                        modified_time=datetime.fromisoformat(
                            folder_data["modifiedTime"].replace("Z", "+00:00")
                        ),
                        web_view_link=folder_data["webViewLink"],
                        parents=folder_data.get("parents", []),
                        file_count=file_count,
                    )
                    drive_folders.append(drive_folder)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse folder {folder_data.get('name', 'unknown')}: {e}"
                    )
                    continue

            logger.info(f"Retrieved {len(drive_folders)} folders from Drive")
            return drive_folders

        except HttpError as e:
            logger.error(f"Drive API error listing folders: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing folders: {e}")
            raise

    def _get_folder_file_count(self, folder_id: str) -> int:
        """Get the number of files in a folder."""
        try:
            results = (
                self.service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    pageSize=1,
                    fields="files(id)",
                )
                .execute()
            )

            # This is a simple count - for large folders, you'd need pagination
            return len(results.get("files", []))

        except Exception as e:
            logger.warning(f"Failed to get file count for folder {folder_id}: {e}")
            return 0

    def find_campaign_files(
        self, campaign_keywords: List[str], folder_id: Optional[str] = None
    ) -> List[DriveFile]:
        """
        Find files that might be related to specific campaigns.

        Args:
            campaign_keywords: Keywords to search for in file names
            folder_id: Optional folder to restrict search to

        Returns:
            List of potential campaign files
        """
        all_files = []

        for keyword in campaign_keywords:
            try:
                files = self.search_files(keyword, limit=20)
                all_files.extend(files)
            except Exception as e:
                logger.warning(f"Failed to search for keyword '{keyword}': {e}")
                continue

        # Remove duplicates by file ID
        unique_files = {file.id: file for file in all_files}

        logger.info(f"Found {len(unique_files)} unique campaign files")
        return list(unique_files.values())
