"""
Google Sheets API Client

Provides methods for reading and writing campaign data from Google Sheets.
Follows FastAPI dependency injection patterns and integrates with auth manager.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.core.config import Settings

from .auth import GoogleAuthManager

logger = logging.getLogger(__name__)


class SheetInfo(BaseModel):
    """Pydantic model for Google Sheet information."""

    spreadsheet_id: str
    title: str
    url: str
    sheets: List[Dict[str, Any]] = []


class SheetData(BaseModel):
    """Pydantic model for sheet data."""

    range: str
    values: List[List[str]] = []
    major_dimension: str = "ROWS"


class CampaignData(BaseModel):
    """Pydantic model for campaign data from sheets."""

    campaign_name: str
    budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    platform: Optional[str] = None
    targeting: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    raw_row: List[str] = []


class GoogleSheetsClient:
    """
    Google Sheets API client for media planning data operations.

    Provides methods for:
    - Reading campaign data from spreadsheets
    - Writing performance metrics
    - Discovering sheet structure
    - Batch operations for efficiency

    Supports context manager usage for proper resource cleanup.
    """

    def __init__(self, auth_manager: GoogleAuthManager, settings: Settings):
        """Initialize the Sheets client."""
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
                logger.warning(f"Error closing Sheets service: {e}")
            finally:
                self._service = None

    @property
    def service(self):
        """Get authenticated Sheets service."""
        if not self._service:
            credentials = self.auth_manager.get_valid_credentials()
            if not credentials:
                raise ValueError("No valid Google credentials available")

            self._service = build(
                "sheets",
                "v4",
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
            logger.error(f"Sheets API error during {operation}: {e}")
            if e.resp.status in [401, 403]:
                # Clear invalid credentials
                self.auth_manager.credentials = None
            raise
        except Exception as e:
            logger.error(f"Unexpected error during {operation}: {e}")
            raise

    def get_spreadsheet_info(self, spreadsheet_id: str) -> SheetInfo:
        """
        Get information about a spreadsheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID

        Returns:
            SheetInfo object with spreadsheet metadata
        """
        with self._handle_api_errors("get_spreadsheet_info"):
            spreadsheet = (
                self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            )

            return SheetInfo(
                spreadsheet_id=spreadsheet_id,
                title=spreadsheet["properties"]["title"],
                url=spreadsheet["spreadsheetUrl"],
                sheets=[
                    {
                        "sheet_id": sheet["properties"]["sheetId"],
                        "title": sheet["properties"]["title"],
                        "grid_properties": sheet["properties"].get(
                            "gridProperties", {}
                        ),
                    }
                    for sheet in spreadsheet.get("sheets", [])
                ],
            )

    def read_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        value_render_option: str = "FORMATTED_VALUE",
    ) -> SheetData:
        """
        Read data from a specific range in a spreadsheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            range_name: A1 notation range (e.g., "Sheet1!A1:D10")
            value_render_option: How values should be represented

        Returns:
            SheetData object with the range data
        """
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueRenderOption=value_render_option,
                )
                .execute()
            )

            return SheetData(
                range=result.get("range", range_name),
                values=result.get("values", []),
                major_dimension=result.get("majorDimension", "ROWS"),
            )

        except HttpError as e:
            logger.error(f"Sheets API error reading range: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading range: {e}")
            raise

    def write_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> Dict[str, Any]:
        """
        Write data to a specific range in a spreadsheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            range_name: A1 notation range
            values: 2D array of values to write
            value_input_option: How input data should be interpreted

        Returns:
            Update response from Sheets API
        """
        try:
            body = {"values": values, "majorDimension": "ROWS"}

            result = (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body=body,
                )
                .execute()
            )

            logger.info(
                f"Updated {result.get('updatedCells', 0)} cells in range {range_name}"
            )
            return result

        except HttpError as e:
            logger.error(f"Sheets API error writing range: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error writing range: {e}")
            raise

    def batch_read(self, spreadsheet_id: str, ranges: List[str]) -> List[SheetData]:
        """
        Read multiple ranges in a single request.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            ranges: List of A1 notation ranges

        Returns:
            List of SheetData objects for each range
        """
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .batchGet(
                    spreadsheetId=spreadsheet_id,
                    ranges=ranges,
                    valueRenderOption="FORMATTED_VALUE",
                )
                .execute()
            )

            sheet_data_list = []
            for value_range in result.get("valueRanges", []):
                sheet_data = SheetData(
                    range=value_range.get("range", ""),
                    values=value_range.get("values", []),
                    major_dimension=value_range.get("majorDimension", "ROWS"),
                )
                sheet_data_list.append(sheet_data)

            logger.info(f"Successfully read {len(sheet_data_list)} ranges")
            return sheet_data_list

        except HttpError as e:
            logger.error(f"Sheets API error in batch read: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in batch read: {e}")
            raise

    def batch_write(
        self, spreadsheet_id: str, updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Write to multiple ranges in a single request.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            updates: List of update objects with 'range' and 'values' keys

        Returns:
            Batch update response from Sheets API
        """
        try:
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {
                        "range": update["range"],
                        "values": update["values"],
                        "majorDimension": "ROWS",
                    }
                    for update in updates
                ],
            }

            result = (
                self.service.spreadsheets()
                .values()
                .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
                .execute()
            )

            total_updated = sum(
                response.get("updatedCells", 0)
                for response in result.get("responses", [])
            )
            logger.info(
                f"Updated {total_updated} total cells across {len(updates)} ranges"
            )
            return result

        except HttpError as e:
            logger.error(f"Sheets API error in batch write: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in batch write: {e}")
            raise

    def parse_campaign_data(
        self,
        spreadsheet_id: str,
        sheet_name: str = "Sheet1",
        header_row: int = 1,
        data_start_row: int = 2,
    ) -> List[CampaignData]:
        """
        Parse campaign data from a standardized sheet format.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet to read
            header_row: Row number containing headers (1-indexed)
            data_start_row: First row containing data (1-indexed)

        Returns:
            List of CampaignData objects
        """
        try:
            # Read headers
            header_range = f"{sheet_name}!{header_row}:{header_row}"
            header_data = self.read_range(spreadsheet_id, header_range)

            if not header_data.values:
                logger.warning("No headers found in spreadsheet")
                return []

            headers = header_data.values[0]
            logger.info(f"Found headers: {headers}")

            # Read all data starting from data_start_row
            data_range = f"{sheet_name}!{data_start_row}:ZZ"
            data_result = self.read_range(spreadsheet_id, data_range)

            campaigns = []
            for row_idx, row in enumerate(data_result.values, start=data_start_row):
                try:
                    # Ensure row has same length as headers
                    padded_row = row + [""] * (len(headers) - len(row))

                    # Create campaign data
                    campaign_data = self._parse_campaign_row(headers, padded_row)
                    campaigns.append(campaign_data)

                except Exception as e:
                    logger.warning(f"Failed to parse row {row_idx}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(campaigns)} campaigns")
            return campaigns

        except HttpError as e:
            logger.error(f"Sheets API error parsing campaign data: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing campaign data: {e}")
            raise

    def _parse_campaign_row(self, headers: List[str], row: List[str]) -> CampaignData:
        """Parse a single campaign row based on headers."""
        # Create a mapping of header to value
        row_data = {
            header.lower().strip(): value for header, value in zip(headers, row)
        }

        # Extract common campaign fields
        campaign_name = (
            row_data.get("campaign_name", "")
            or row_data.get("name", "")
            or row_data.get("campaign", "")
        )

        # Try to parse budget
        budget = None
        budget_str = row_data.get("budget", "") or row_data.get("total_budget", "")
        if budget_str:
            try:
                # Remove currency symbols and commas
                clean_budget = budget_str.replace("$", "").replace(",", "").strip()
                budget = float(clean_budget)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse budget: {budget_str}")

        # Extract dates
        start_date = row_data.get("start_date", "") or row_data.get("launch_date", "")
        end_date = row_data.get("end_date", "") or row_data.get("completion_date", "")

        # Extract platform
        platform = (
            row_data.get("platform", "")
            or row_data.get("channel", "")
            or row_data.get("media_type", "")
        )

        # Extract targeting info (store as dict)
        targeting = {}
        for key, value in row_data.items():
            if any(
                target_key in key
                for target_key in ["target", "audience", "demographic"]
            ):
                if value.strip():
                    targeting[key] = value

        # Extract metrics (store as dict)
        metrics = {}
        for key, value in row_data.items():
            if any(
                metric_key in key
                for metric_key in [
                    "impression",
                    "click",
                    "conversion",
                    "ctr",
                    "cpc",
                    "cpm",
                ]
            ):
                if value.strip():
                    try:
                        # Try to convert to float if it's a number
                        clean_value = value.replace("%", "").replace(",", "").strip()
                        metrics[key] = float(clean_value)
                    except (ValueError, TypeError):
                        metrics[key] = value

        return CampaignData(
            campaign_name=campaign_name,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
            platform=platform,
            targeting=targeting,
            metrics=metrics,
            raw_row=row,
        )

    def find_campaign_sheets(self, drive_client) -> List[SheetInfo]:
        """
        Find spreadsheets that might contain campaign data.

        Args:
            drive_client: GoogleDriveClient instance for file discovery

        Returns:
            List of SheetInfo objects for potential campaign sheets
        """
        try:
            # Search for spreadsheet files with campaign-related keywords
            campaign_keywords = ["campaign", "media", "planning", "budget", "ads"]

            # Get Google Sheets MIME type
            sheets_mime_type = "application/vnd.google-apps.spreadsheet"

            sheet_files = drive_client.list_files(
                file_types=[sheets_mime_type], limit=50
            )

            # Filter for files that might contain campaign data
            campaign_sheets = []
            for sheet_file in sheet_files:
                name_lower = sheet_file.name.lower()
                if any(keyword in name_lower for keyword in campaign_keywords):
                    try:
                        sheet_info = self.get_spreadsheet_info(sheet_file.id)
                        campaign_sheets.append(sheet_info)
                    except Exception as e:
                        logger.warning(
                            f"Could not get info for sheet {sheet_file.name}: {e}"
                        )
                        continue

            logger.info(f"Found {len(campaign_sheets)} potential campaign spreadsheets")
            return campaign_sheets

        except Exception as e:
            logger.error(f"Error finding campaign sheets: {e}")
            return []
