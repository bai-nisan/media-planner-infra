"""
Workspace Tools for LangGraph Multi-Agent System

Tools for Google Sheets reading, file parsing, data validation, and workspace management.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.google.auth import GoogleAuthManager
from app.services.google.drive_client import GoogleDriveClient

# Add imports for real Google API integration
from app.services.google.sheets_client import CampaignData, GoogleSheetsClient

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all tools."""

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the tool."""
        pass


class GoogleSheetsReader(BaseTool):
    """Tool for reading data from Google Sheets using real Google Sheets API."""

    def __init__(self, auth_manager: Optional[GoogleAuthManager] = None, settings=None):
        self.name = "google_sheets_reader"
        self.description = "Reads data from Google Sheets using the Google Sheets API"

        # Initialize dependencies
        if settings is None:
            settings = get_settings()
        if auth_manager is None:
            auth_manager = GoogleAuthManager(settings)

        self.auth_manager = auth_manager
        self.settings = settings
        self._sheets_client = None
        self._drive_client = None

    @property
    def sheets_client(self) -> GoogleSheetsClient:
        """Get or create GoogleSheetsClient instance."""
        if self._sheets_client is None:
            self._sheets_client = GoogleSheetsClient(self.auth_manager, self.settings)
        return self._sheets_client

    @property
    def drive_client(self) -> GoogleDriveClient:
        """Get or create GoogleDriveClient instance."""
        if self._drive_client is None:
            self._drive_client = GoogleDriveClient(self.auth_manager, self.settings)
        return self._drive_client

    async def extract_data(
        self, spreadsheet_id: str, sheet_range: str = "A1:Z1000"
    ) -> Dict[str, Any]:
        """Extract data from a Google Sheet using real API."""
        try:
            logger.info(
                f"Extracting data from sheet {spreadsheet_id}, range {sheet_range}"
            )

            # Check authentication first
            if not self.auth_manager.is_authenticated():
                raise ValueError(
                    "Google API authentication required. Please authenticate first."
                )

            with self.sheets_client as sheets:
                # Get spreadsheet info
                sheet_info = sheets.get_spreadsheet_info(spreadsheet_id)
                logger.info(f"Processing spreadsheet: {sheet_info.title}")

                # Read the specified range
                sheet_data = sheets.read_range(spreadsheet_id, sheet_range)

                if not sheet_data.values:
                    logger.warning(f"No data found in range {sheet_range}")
                    return {
                        "spreadsheet_id": spreadsheet_id,
                        "range": sheet_range,
                        "rows": [],
                        "headers": [],
                        "extraction_metadata": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "row_count": 0,
                            "column_count": 0,
                            "status": "no_data_found",
                        },
                    }

                # Extract headers and data rows
                rows = sheet_data.values
                headers = rows[0] if rows else []

                # Parse campaign data using the sheets client's built-in parser
                try:
                    campaign_data = sheets.parse_campaign_data(
                        spreadsheet_id=spreadsheet_id,
                        sheet_name=(
                            sheet_range.split("!")[0]
                            if "!" in sheet_range
                            else "Sheet1"
                        ),
                    )

                    # Convert CampaignData objects to dictionaries
                    parsed_campaigns = [
                        {
                            "campaign_name": campaign.campaign_name,
                            "budget": campaign.budget,
                            "start_date": campaign.start_date,
                            "end_date": campaign.end_date,
                            "platform": campaign.platform,
                            "targeting": campaign.targeting,
                            "metrics": campaign.metrics,
                            "raw_row": campaign.raw_row,
                        }
                        for campaign in campaign_data
                    ]

                    logger.info(
                        f"Successfully parsed {len(parsed_campaigns)} campaigns from spreadsheet"
                    )

                except Exception as parse_error:
                    logger.warning(f"Failed to parse campaign data: {parse_error}")
                    parsed_campaigns = []

                return {
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_title": sheet_info.title,
                    "spreadsheet_url": sheet_info.url,
                    "range": sheet_range,
                    "rows": rows,
                    "headers": headers,
                    "parsed_campaigns": parsed_campaigns,
                    "extraction_metadata": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "row_count": len(rows),
                        "column_count": len(headers),
                        "campaigns_parsed": len(parsed_campaigns),
                        "status": "success",
                    },
                }

        except ValueError as ve:
            logger.error(f"Authentication error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error extracting Google Sheets data: {e}")
            # Return error information instead of raising to allow graceful handling
            return {
                "spreadsheet_id": spreadsheet_id,
                "range": sheet_range,
                "rows": [],
                "headers": [],
                "extraction_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "row_count": 0,
                    "column_count": 0,
                    "status": "error",
                    "error_message": str(e),
                },
            }

    async def discover_campaign_sheets(self) -> Dict[str, Any]:
        """Discover spreadsheets that might contain campaign data."""
        try:
            logger.info("Discovering campaign-related spreadsheets")

            if not self.auth_manager.is_authenticated():
                raise ValueError(
                    "Google API authentication required. Please authenticate first."
                )

            with self.drive_client as drive, self.sheets_client as sheets:
                # Find campaign-related spreadsheets
                campaign_sheets = sheets.find_campaign_sheets(drive)

                discovery_results = []
                for sheet_info in campaign_sheets:
                    discovery_results.append(
                        {
                            "spreadsheet_id": sheet_info.spreadsheet_id,
                            "title": sheet_info.title,
                            "url": sheet_info.url,
                            "sheets": sheet_info.sheets,
                        }
                    )

                logger.info(
                    f"Discovered {len(discovery_results)} potential campaign spreadsheets"
                )

                return {
                    "discovered_sheets": discovery_results,
                    "discovery_metadata": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "sheets_found": len(discovery_results),
                        "status": "success",
                    },
                }

        except ValueError as ve:
            logger.error(f"Authentication error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error discovering campaign sheets: {e}")
            return {
                "discovered_sheets": [],
                "discovery_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "sheets_found": 0,
                    "status": "error",
                    "error_message": str(e),
                },
            }

    async def execute(
        self, spreadsheet_id: str, sheet_range: str = "A1:Z1000"
    ) -> Dict[str, Any]:
        """Execute the Google Sheets reader tool."""
        return await self.extract_data(spreadsheet_id, sheet_range)


class FileParser(BaseTool):
    """Tool for parsing various file formats and integrating with Google Drive."""

    def __init__(self, auth_manager: Optional[GoogleAuthManager] = None, settings=None):
        self.name = "file_parser"
        self.description = "Parses various file formats including CSV, Excel, JSON, and XML from Google Drive or local files"
        self.supported_formats = ["csv", "xlsx", "json", "xml", "txt", "sheets"]

        # Initialize dependencies for Google Drive integration
        if settings is None:
            settings = get_settings()
        if auth_manager is None:
            auth_manager = GoogleAuthManager(settings)

        self.auth_manager = auth_manager
        self.settings = settings
        self._drive_client = None
        self._sheets_reader = None

    @property
    def drive_client(self) -> GoogleDriveClient:
        """Get or create GoogleDriveClient instance."""
        if self._drive_client is None:
            self._drive_client = GoogleDriveClient(self.auth_manager, self.settings)
        return self._drive_client

    @property
    def sheets_reader(self) -> GoogleSheetsReader:
        """Get or create GoogleSheetsReader instance."""
        if self._sheets_reader is None:
            self._sheets_reader = GoogleSheetsReader(self.auth_manager, self.settings)
        return self._sheets_reader

    async def parse_google_drive_file(self, file_id: str) -> Dict[str, Any]:
        """Parse a file from Google Drive."""
        try:
            logger.info(f"Parsing Google Drive file {file_id}")

            if not self.auth_manager.is_authenticated():
                raise ValueError(
                    "Google API authentication required. Please authenticate first."
                )

            with self.drive_client as drive:
                # Get file metadata
                file_metadata = drive.get_file_metadata(file_id)
                if not file_metadata:
                    raise ValueError(f"File {file_id} not found in Google Drive")

                logger.info(
                    f"Processing file: {file_metadata.name} ({file_metadata.mime_type})"
                )

                # Handle Google Sheets
                if file_metadata.mime_type == "application/vnd.google-apps.spreadsheet":
                    return await self._parse_google_sheet(file_id)

                # Handle other file types (future implementation)
                else:
                    return {
                        "file_id": file_id,
                        "file_name": file_metadata.name,
                        "file_type": file_metadata.mime_type,
                        "parsing_status": "unsupported",
                        "message": f"File type {file_metadata.mime_type} not yet supported for parsing",
                        "parsing_metadata": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "file_size": file_metadata.size,
                            "records_parsed": 0,
                        },
                    }

        except ValueError as ve:
            logger.error(f"Authentication or file error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error parsing Google Drive file: {e}")
            return {
                "file_id": file_id,
                "parsing_status": "error",
                "error_message": str(e),
                "parsing_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    async def _parse_google_sheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Parse a Google Sheet using the GoogleSheetsReader."""
        try:
            # Use the GoogleSheetsReader to extract data
            sheet_data = await self.sheets_reader.extract_data(spreadsheet_id)

            return {
                "file_id": spreadsheet_id,
                "file_type": "google_sheets",
                "parsing_status": "success",
                "parsed_data": {
                    "campaigns": sheet_data.get("parsed_campaigns", []),
                    "raw_data": {
                        "rows": sheet_data.get("rows", []),
                        "headers": sheet_data.get("headers", []),
                    },
                    "spreadsheet_info": {
                        "title": sheet_data.get("spreadsheet_title", ""),
                        "url": sheet_data.get("spreadsheet_url", ""),
                    },
                },
                "parsing_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "records_parsed": len(sheet_data.get("parsed_campaigns", [])),
                    "extraction_metadata": sheet_data.get("extraction_metadata", {}),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing Google Sheet {spreadsheet_id}: {e}")
            return {
                "file_id": spreadsheet_id,
                "file_type": "google_sheets",
                "parsing_status": "error",
                "error_message": str(e),
                "parsing_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    async def parse_file(
        self, file_path: str, file_type: str = "auto"
    ) -> Dict[str, Any]:
        """Parse a file and return structured data."""
        try:
            logger.info(f"Parsing file {file_path} as {file_type}")

            # Check if this is a Google Drive file ID or Sheets URL
            if self._is_google_drive_id(file_path):
                return await self.parse_google_drive_file(file_path)
            elif self._is_google_sheets_url(file_path):
                spreadsheet_id = self._extract_spreadsheet_id(file_path)
                return await self._parse_google_sheet(spreadsheet_id)

            # For local files, return a placeholder implementation
            # This would be enhanced to handle actual local file parsing
            logger.warning(f"Local file parsing not yet implemented for {file_path}")
            return {
                "file_path": file_path,
                "file_type": file_type,
                "parsing_status": "not_implemented",
                "message": "Local file parsing not yet implemented. Use Google Drive files instead.",
                "parsing_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "records_parsed": 0,
                },
            }

        except Exception as e:
            logger.error(f"Error parsing file: {e}")
            return {
                "file_path": file_path,
                "file_type": file_type,
                "parsing_status": "error",
                "error_message": str(e),
                "parsing_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    def _is_google_drive_id(self, file_path: str) -> bool:
        """Check if the file_path is a Google Drive file ID."""
        # Google Drive file IDs are typically 33-44 characters long and alphanumeric with underscores/hyphens
        import re

        pattern = r"^[a-zA-Z0-9_-]{28,}$"
        return bool(re.match(pattern, file_path))

    def _is_google_sheets_url(self, file_path: str) -> bool:
        """Check if the file_path is a Google Sheets URL."""
        return "docs.google.com/spreadsheets" in file_path

    def _extract_spreadsheet_id(self, sheets_url: str) -> str:
        """Extract spreadsheet ID from Google Sheets URL."""
        import re

        pattern = r"/spreadsheets/d/([a-zA-Z0-9-_]+)"
        match = re.search(pattern, sheets_url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract spreadsheet ID from URL: {sheets_url}")

    async def execute(self, file_path: str, file_type: str = "auto") -> Dict[str, Any]:
        """Execute the file parser tool."""
        return await self.parse_file(file_path, file_type)


class DataValidator(BaseTool):
    """Tool for validating data integrity and format."""

    def __init__(self):
        self.name = "data_validator"
        self.description = "Validates data integrity, format, and business rules"
        self.validation_rules = {
            "campaign_data": {
                "required_fields": ["campaign_name", "budget", "platform"],
                "budget_min": 1000,
                "budget_max": 1000000,
                "valid_platforms": [
                    "Google Ads",
                    "Meta Ads",
                    "LinkedIn Ads",
                    "Twitter Ads",
                    "Facebook Ads",
                    "Instagram Ads",
                ],
            },
            "sheet_data": {
                "min_rows": 2,  # At least header + 1 data row
                "max_rows": 10000,
                "required_headers": ["Campaign", "Budget"],
            },
        }

    async def validate_extracted_sheet_data(
        self, sheet_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate Google Sheets data from the new extract_data format."""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "validated_fields": [],
                "data_quality_score": 0.0,
            }

            # Check if extraction was successful
            extraction_metadata = sheet_data.get("extraction_metadata", {})
            if extraction_metadata.get("status") == "error":
                validation_result["errors"].append(
                    f"Data extraction failed: {extraction_metadata.get('error_message', 'Unknown error')}"
                )
                validation_result["is_valid"] = False
                return validation_result
            elif extraction_metadata.get("status") == "no_data_found":
                validation_result["warnings"].append(
                    "No data found in the specified range"
                )
                validation_result["data_quality_score"] = 0.0
                return validation_result

            rows = sheet_data.get("rows", [])
            headers = sheet_data.get("headers", [])
            parsed_campaigns = sheet_data.get("parsed_campaigns", [])

            # Validate basic structure
            if len(rows) < self.validation_rules["sheet_data"]["min_rows"]:
                validation_result["errors"].append(
                    f"Insufficient data rows. Found {len(rows)}, minimum required: {self.validation_rules['sheet_data']['min_rows']}"
                )
                validation_result["is_valid"] = False

            # Validate headers
            for required_header in self.validation_rules["sheet_data"][
                "required_headers"
            ]:
                header_found = any(
                    required_header.lower() in header.lower() for header in headers
                )
                if not header_found:
                    validation_result["errors"].append(
                        f"Missing required header containing: {required_header}"
                    )
                    validation_result["is_valid"] = False
                else:
                    validation_result["validated_fields"].append(
                        f"header_{required_header}"
                    )

            # Validate parsed campaigns
            campaigns_validated = 0
            for i, campaign in enumerate(parsed_campaigns):
                campaign_valid = True

                # Check required fields
                for field in self.validation_rules["campaign_data"]["required_fields"]:
                    if not campaign.get(field):
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Missing or empty required field '{field}'"
                        )
                        campaign_valid = False
                    else:
                        validation_result["validated_fields"].append(
                            f"campaign_{i+1}_{field}"
                        )

                # Validate budget
                budget = campaign.get("budget")
                if budget is not None:
                    if budget < self.validation_rules["campaign_data"]["budget_min"]:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Budget ${budget} is below recommended minimum ${self.validation_rules['campaign_data']['budget_min']}"
                        )
                    elif budget > self.validation_rules["campaign_data"]["budget_max"]:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Budget ${budget} exceeds maximum ${self.validation_rules['campaign_data']['budget_max']}"
                        )

                # Validate platform
                platform = campaign.get("platform")
                if platform:
                    valid_platforms = self.validation_rules["campaign_data"][
                        "valid_platforms"
                    ]
                    if platform not in valid_platforms:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Platform '{platform}' not in standard list: {valid_platforms}"
                        )

                # Validate dates
                start_date = campaign.get("start_date")
                end_date = campaign.get("end_date")
                if start_date and end_date:
                    try:
                        # Basic date validation - could be enhanced with proper date parsing
                        if len(start_date) < 8 or len(end_date) < 8:
                            validation_result["warnings"].append(
                                f"Campaign {i+1}: Date format may be invalid"
                            )
                    except Exception:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Could not validate date format"
                        )

                if campaign_valid:
                    campaigns_validated += 1

            # Calculate data quality score
            total_campaigns = len(parsed_campaigns)
            if total_campaigns > 0:
                validation_result["data_quality_score"] = (
                    campaigns_validated / total_campaigns
                )
            else:
                validation_result["data_quality_score"] = 0.0

            # Overall validation status
            if validation_result["data_quality_score"] < 0.5 and total_campaigns > 0:
                validation_result["is_valid"] = False
                validation_result["errors"].append(
                    "Data quality score is below acceptable threshold (50%)"
                )

            validation_result["validation_metadata"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "rows_validated": len(rows),
                "headers_validated": len(headers),
                "campaigns_validated": campaigns_validated,
                "total_campaigns": total_campaigns,
                "data_quality_score": validation_result["data_quality_score"],
            }

            return validation_result

        except Exception as e:
            logger.error(f"Error validating extracted sheet data: {e}")
            return {
                "is_valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "validated_fields": [],
                "data_quality_score": 0.0,
                "validation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "validation_error": str(e),
                },
            }

    async def validate_sheet_data(self, sheet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Google Sheets data (legacy format support)."""
        try:
            # Check if this is the new format from extract_data
            if "extraction_metadata" in sheet_data:
                return await self.validate_extracted_sheet_data(sheet_data)

            # Legacy validation for old format
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "validated_fields": [],
            }

            rows = sheet_data.get("rows", [])
            headers = sheet_data.get("headers", [])

            # Check minimum rows
            if len(rows) < self.validation_rules["sheet_data"]["min_rows"]:
                validation_result["errors"].append(
                    f"Insufficient data rows. Found {len(rows)}, minimum required: {self.validation_rules['sheet_data']['min_rows']}"
                )
                validation_result["is_valid"] = False

            # Check required headers
            for required_header in self.validation_rules["sheet_data"][
                "required_headers"
            ]:
                if required_header not in headers:
                    validation_result["errors"].append(
                        f"Missing required header: {required_header}"
                    )
                    validation_result["is_valid"] = False
                else:
                    validation_result["validated_fields"].append(required_header)

            # Check for empty cells in critical columns
            if "Budget" in headers:
                budget_col_index = headers.index("Budget")
                for i, row in enumerate(rows[1:], 1):  # Skip header row
                    if len(row) <= budget_col_index or not row[budget_col_index]:
                        validation_result["warnings"].append(
                            f"Empty budget value in row {i+1}"
                        )

            validation_result["validation_metadata"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "rows_validated": len(rows),
                "headers_validated": len(headers),
            }

            return validation_result

        except Exception as e:
            logger.error(f"Error validating sheet data: {e}")
            raise

    async def validate_campaign_data(
        self, campaign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate campaign data."""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "validated_fields": [],
            }

            # Handle new format with parsed_campaigns
            if "parsed_campaigns" in campaign_data:
                campaigns = campaign_data["parsed_campaigns"]
            else:
                # Legacy format
                parsed_data = campaign_data.get("parsed_data", {})
                campaigns = parsed_data.get("campaigns", [])

            for i, campaign in enumerate(campaigns):
                # Check required fields
                for field in self.validation_rules["campaign_data"]["required_fields"]:
                    # Handle both old and new field names
                    value = campaign.get(field) or campaign.get(
                        field.replace("campaign_", "")
                    )
                    if not value:
                        validation_result["errors"].append(
                            f"Campaign {i+1}: Missing required field '{field}'"
                        )
                        validation_result["is_valid"] = False
                    else:
                        validation_result["validated_fields"].append(
                            f"campaign_{i+1}_{field}"
                        )

                # Validate budget range
                budget = campaign.get("budget")
                if budget:
                    if budget < self.validation_rules["campaign_data"]["budget_min"]:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Budget ${budget} is below recommended minimum ${self.validation_rules['campaign_data']['budget_min']}"
                        )
                    elif budget > self.validation_rules["campaign_data"]["budget_max"]:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Budget ${budget} exceeds maximum ${self.validation_rules['campaign_data']['budget_max']}"
                        )

                # Validate platform
                platform = campaign.get("platform")
                if platform:
                    valid_platforms = self.validation_rules["campaign_data"][
                        "valid_platforms"
                    ]
                    if platform not in valid_platforms:
                        validation_result["warnings"].append(
                            f"Campaign {i+1}: Platform '{platform}' not in standard list: {valid_platforms}"
                        )

            validation_result["validation_metadata"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "campaigns_validated": len(campaigns),
            }

            return validation_result

        except Exception as e:
            logger.error(f"Error validating campaign data: {e}")
            raise

    async def validate_data(
        self, data: Dict[str, Any], validation_type: str
    ) -> Dict[str, Any]:
        """Generic data validation."""
        if validation_type == "sheet_data":
            return await self.validate_sheet_data(data)
        elif validation_type == "campaign_data":
            return await self.validate_campaign_data(data)
        elif validation_type == "extracted_sheet_data":
            return await self.validate_extracted_sheet_data(data)
        else:
            # General validation
            return {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "message": f"No specific validation rules for type: {validation_type}",
                "validation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "validation_type": validation_type,
                },
            }

    async def execute(
        self, data: Dict[str, Any], validation_type: str = "general"
    ) -> Dict[str, Any]:
        """Execute the data validator tool."""
        return await self.validate_data(data, validation_type)


class WorkspaceManager(BaseTool):
    """Tool for managing workspace operations with Google API integration."""

    def __init__(self, auth_manager: Optional[GoogleAuthManager] = None, settings=None):
        self.name = "workspace_manager"
        self.description = "Manages workspace operations including file organization, data synchronization, and Google API coordination"
        self.supported_operations = [
            "discover_campaign_files",
            "organize_files",
            "sync_data",
            "validate_workspace",
            "setup_workspace",
        ]

        # Initialize dependencies
        if settings is None:
            settings = get_settings()
        if auth_manager is None:
            auth_manager = GoogleAuthManager(settings)

        self.auth_manager = auth_manager
        self.settings = settings
        self._drive_client = None
        self._sheets_reader = None
        self._file_parser = None
        self._data_validator = None

    @property
    def drive_client(self) -> GoogleDriveClient:
        """Get or create GoogleDriveClient instance."""
        if self._drive_client is None:
            self._drive_client = GoogleDriveClient(self.auth_manager, self.settings)
        return self._drive_client

    @property
    def sheets_reader(self) -> GoogleSheetsReader:
        """Get or create GoogleSheetsReader instance."""
        if self._sheets_reader is None:
            self._sheets_reader = GoogleSheetsReader(self.auth_manager, self.settings)
        return self._sheets_reader

    @property
    def file_parser(self) -> FileParser:
        """Get or create FileParser instance."""
        if self._file_parser is None:
            self._file_parser = FileParser(self.auth_manager, self.settings)
        return self._file_parser

    @property
    def data_validator(self) -> DataValidator:
        """Get or create DataValidator instance."""
        if self._data_validator is None:
            self._data_validator = DataValidator()
        return self._data_validator

    async def discover_campaign_files(self) -> Dict[str, Any]:
        """Discover campaign-related files in Google Drive."""
        try:
            logger.info("Discovering campaign files in workspace")

            if not self.auth_manager.is_authenticated():
                raise ValueError(
                    "Google API authentication required. Please authenticate first."
                )

            # Discover campaign sheets
            discovery_result = await self.sheets_reader.discover_campaign_sheets()

            # Get additional file information from Drive
            with self.drive_client as drive:
                # Search for additional campaign-related files
                campaign_keywords = [
                    "campaign",
                    "media",
                    "planning",
                    "budget",
                    "ads",
                    "marketing",
                ]
                campaign_files = drive.find_campaign_files(campaign_keywords)

                # Filter out spreadsheets (already found by sheets_reader)
                non_sheet_files = [
                    {
                        "file_id": file.id,
                        "name": file.name,
                        "mime_type": file.mime_type,
                        "size": file.size,
                        "modified_time": file.modified_time.isoformat(),
                        "web_view_link": file.web_view_link,
                    }
                    for file in campaign_files
                    if file.mime_type != "application/vnd.google-apps.spreadsheet"
                ]

            return {
                "operation": "discover_campaign_files",
                "status": "completed",
                "discovered_spreadsheets": discovery_result.get(
                    "discovered_sheets", []
                ),
                "discovered_files": non_sheet_files,
                "operation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "spreadsheets_found": len(
                        discovery_result.get("discovered_sheets", [])
                    ),
                    "other_files_found": len(non_sheet_files),
                },
            }

        except ValueError as ve:
            logger.error(f"Authentication error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error discovering campaign files: {e}")
            return {
                "operation": "discover_campaign_files",
                "status": "error",
                "error_message": str(e),
                "operation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    async def validate_workspace(
        self, discovered_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate the workspace data quality."""
        try:
            logger.info("Validating workspace data")

            validation_results = []
            overall_valid = True

            for file_info in discovered_files:
                if (
                    file_info.get("mime_type")
                    == "application/vnd.google-apps.spreadsheet"
                ):
                    # Validate spreadsheet data
                    try:
                        sheet_data = await self.sheets_reader.extract_data(
                            file_info["spreadsheet_id"]
                        )
                        validation_result = await self.data_validator.validate_data(
                            sheet_data, "extracted_sheet_data"
                        )
                        validation_result["file_info"] = file_info
                        validation_results.append(validation_result)

                        if not validation_result["is_valid"]:
                            overall_valid = False

                    except Exception as e:
                        logger.warning(
                            f"Failed to validate {file_info.get('title', 'unknown')}: {e}"
                        )
                        validation_results.append(
                            {
                                "is_valid": False,
                                "errors": [f"Validation failed: {str(e)}"],
                                "file_info": file_info,
                            }
                        )
                        overall_valid = False

            return {
                "operation": "validate_workspace",
                "status": "completed",
                "overall_valid": overall_valid,
                "validation_results": validation_results,
                "operation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "files_validated": len(validation_results),
                    "files_passed": sum(1 for r in validation_results if r["is_valid"]),
                },
            }

        except Exception as e:
            logger.error(f"Error validating workspace: {e}")
            return {
                "operation": "validate_workspace",
                "status": "error",
                "error_message": str(e),
                "operation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    async def execute_operation(
        self, operation: str, operation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a workspace operation."""
        try:
            logger.info(f"Executing workspace operation: {operation}")

            if operation not in self.supported_operations:
                raise ValueError(f"Unsupported operation: {operation}")

            if operation == "discover_campaign_files":
                return await self.discover_campaign_files()

            elif operation == "validate_workspace":
                discovered_files = operation_data.get("discovered_files", [])
                return await self.validate_workspace(discovered_files)

            elif operation == "setup_workspace":
                # Comprehensive workspace setup
                discovery_result = await self.discover_campaign_files()
                validation_result = await self.validate_workspace(
                    discovery_result.get("discovered_spreadsheets", [])
                )

                return {
                    "operation": "setup_workspace",
                    "status": "completed",
                    "discovery": discovery_result,
                    "validation": validation_result,
                    "workspace_ready": validation_result.get("overall_valid", False),
                    "operation_metadata": {"timestamp": datetime.utcnow().isoformat()},
                }

            else:
                # Placeholder for other operations
                return {
                    "operation": operation,
                    "status": "not_implemented",
                    "message": f"Operation {operation} not yet implemented",
                    "operation_metadata": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "operation_data": operation_data,
                    },
                }

        except ValueError as ve:
            logger.error(f"Operation error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error executing workspace operation: {e}")
            return {
                "operation": operation,
                "status": "error",
                "error_message": str(e),
                "operation_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            }

    async def execute(
        self, operation: str, operation_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute the workspace manager tool."""
        if operation_data is None:
            operation_data = {}
        return await self.execute_operation(operation, operation_data)
