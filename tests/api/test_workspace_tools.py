"""
Test suite for Workspace Tools

Tests for GoogleSheetsReader, FileParser, DataValidator, and WorkspaceManager
with real Google API integration patterns and comprehensive coverage.
"""

from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.config import Settings
from app.services.google.auth import GoogleAuthManager
from app.services.google.drive_client import GoogleDriveClient
from app.services.google.sheets_client import CampaignData, GoogleSheetsClient
from app.services.langgraph.tools.workspace_tools import (
    DataValidator,
    FileParser,
    GoogleSheetsReader,
    WorkspaceManager,
)


class TestGoogleSheetsReader:
    """Test suite for GoogleSheetsReader tool."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = Mock(spec=Settings)
        settings.GOOGLE_OAUTH_CLIENT_ID = "test_client_id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "test_client_secret"
        return settings

    @pytest.fixture
    def mock_auth_manager(self, mock_settings):
        """Mock authenticated GoogleAuthManager."""
        auth_manager = Mock(spec=GoogleAuthManager)
        auth_manager.is_authenticated.return_value = True
        auth_manager.get_valid_credentials.return_value = Mock()
        return auth_manager

    @pytest.fixture
    def sheets_reader(self, mock_auth_manager, mock_settings):
        """Create GoogleSheetsReader with mocked dependencies."""
        return GoogleSheetsReader(
            auth_manager=mock_auth_manager, settings=mock_settings
        )

    @pytest.fixture
    def sample_sheet_data(self):
        """Sample sheet data for testing."""
        return {
            "values": [
                ["Campaign Name", "Budget", "Platform", "Start Date", "End Date"],
                ["Summer Sale", "50000", "Google Ads", "2024-06-01", "2024-08-31"],
                ["Winter Promo", "75000", "Meta Ads", "2024-12-01", "2024-12-31"],
            ]
        }

    @pytest.fixture
    def sample_campaign_data(self):
        """Sample campaign data objects."""
        return [
            CampaignData(
                campaign_name="Summer Sale",
                budget=50000.0,
                platform="Google Ads",
                start_date="2024-06-01",
                end_date="2024-08-31",
                targeting={},
                metrics={},
                raw_row=[
                    "Summer Sale",
                    "50000",
                    "Google Ads",
                    "2024-06-01",
                    "2024-08-31",
                ],
            ),
            CampaignData(
                campaign_name="Winter Promo",
                budget=75000.0,
                platform="Meta Ads",
                start_date="2024-12-01",
                end_date="2024-12-31",
                targeting={},
                metrics={},
                raw_row=[
                    "Winter Promo",
                    "75000",
                    "Meta Ads",
                    "2024-12-01",
                    "2024-12-31",
                ],
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialization(self, mock_auth_manager, mock_settings):
        """Test proper initialization of GoogleSheetsReader."""
        reader = GoogleSheetsReader(
            auth_manager=mock_auth_manager, settings=mock_settings
        )

        assert reader.name == "google_sheets_reader"
        assert "Google Sheets API" in reader.description
        assert reader.auth_manager == mock_auth_manager
        assert reader.settings == mock_settings

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, sheets_reader, sample_sheet_data, sample_campaign_data
    ):
        """Test successful data extraction from Google Sheets."""
        spreadsheet_id = "test_sheet_id_123"
        sheet_range = "A1:Z1000"

        # Mock the sheets client
        mock_sheets_client = Mock(spec=GoogleSheetsClient)
        mock_sheet_info = Mock()
        mock_sheet_info.title = "Campaign Planning 2024"
        mock_sheet_info.url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        mock_sheets_client.get_spreadsheet_info.return_value = mock_sheet_info
        mock_sheets_client.read_range.return_value = Mock(
            values=sample_sheet_data["values"]
        )
        mock_sheets_client.parse_campaign_data.return_value = sample_campaign_data
        mock_sheets_client.__enter__.return_value = mock_sheets_client
        mock_sheets_client.__exit__.return_value = None

        sheets_reader._sheets_client = mock_sheets_client

        result = await sheets_reader.extract_data(spreadsheet_id, sheet_range)

        # Verify result structure
        assert result["spreadsheet_id"] == spreadsheet_id
        assert result["spreadsheet_title"] == "Campaign Planning 2024"
        assert result["range"] == sheet_range
        assert len(result["rows"]) == 3
        assert len(result["headers"]) == 5
        assert len(result["parsed_campaigns"]) == 2
        assert result["extraction_metadata"]["status"] == "success"
        assert result["extraction_metadata"]["campaigns_parsed"] == 2

        # Verify campaign data structure
        campaign = result["parsed_campaigns"][0]
        assert campaign["campaign_name"] == "Summer Sale"
        assert campaign["budget"] == 50000.0
        assert campaign["platform"] == "Google Ads"

    @pytest.mark.asyncio
    async def test_extract_data_authentication_error(self, sheets_reader):
        """Test handling of authentication errors."""
        sheets_reader.auth_manager.is_authenticated.return_value = False

        with pytest.raises(ValueError, match="authentication required"):
            await sheets_reader.extract_data("test_sheet_id", "A1:Z1000")

    @pytest.mark.asyncio
    async def test_extract_data_no_data_found(self, sheets_reader):
        """Test handling when no data is found in the range."""
        spreadsheet_id = "test_sheet_id_123"

        # Mock empty response
        mock_sheets_client = Mock(spec=GoogleSheetsClient)
        mock_sheet_info = Mock()
        mock_sheet_info.title = "Empty Sheet"
        mock_sheet_info.url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        mock_sheets_client.get_spreadsheet_info.return_value = mock_sheet_info
        mock_sheets_client.read_range.return_value = Mock(values=None)
        mock_sheets_client.__enter__.return_value = mock_sheets_client
        mock_sheets_client.__exit__.return_value = None

        sheets_reader._sheets_client = mock_sheets_client

        result = await sheets_reader.extract_data(spreadsheet_id)

        assert result["extraction_metadata"]["status"] == "no_data_found"
        assert len(result["rows"]) == 0
        assert len(result["headers"]) == 0

    @pytest.mark.asyncio
    async def test_extract_data_api_error(self, sheets_reader):
        """Test handling of API errors."""
        spreadsheet_id = "invalid_sheet_id"

        # Mock API error
        mock_sheets_client = Mock(spec=GoogleSheetsClient)
        mock_sheets_client.get_spreadsheet_info.side_effect = Exception(
            "API Error: Sheet not found"
        )
        mock_sheets_client.__enter__.return_value = mock_sheets_client
        mock_sheets_client.__exit__.return_value = None

        sheets_reader._sheets_client = mock_sheets_client

        result = await sheets_reader.extract_data(spreadsheet_id)

        # Should return error result instead of raising
        assert result["extraction_metadata"]["status"] == "error"
        assert "API Error" in result["extraction_metadata"]["error_message"]

    @pytest.mark.asyncio
    async def test_discover_campaign_sheets(self, sheets_reader):
        """Test discovering campaign-related spreadsheets."""
        # Mock discovery results
        mock_sheet_infos = [
            Mock(
                spreadsheet_id="sheet1",
                title="Campaign Q1 2024",
                url="https://docs.google.com/spreadsheets/d/sheet1",
                sheets=["Campaign Data", "Budget"],
            ),
            Mock(
                spreadsheet_id="sheet2",
                title="Media Planning",
                url="https://docs.google.com/spreadsheets/d/sheet2",
                sheets=["Overview", "Channels"],
            ),
        ]

        mock_sheets_client = Mock(spec=GoogleSheetsClient)
        mock_drive_client = Mock(spec=GoogleDriveClient)
        mock_sheets_client.find_campaign_sheets.return_value = mock_sheet_infos
        mock_sheets_client.__enter__.return_value = mock_sheets_client
        mock_sheets_client.__exit__.return_value = None
        mock_drive_client.__enter__.return_value = mock_drive_client
        mock_drive_client.__exit__.return_value = None

        sheets_reader._sheets_client = mock_sheets_client
        sheets_reader._drive_client = mock_drive_client

        result = await sheets_reader.discover_campaign_sheets()

        assert len(result["discovered_sheets"]) == 2
        assert result["discovery_metadata"]["sheets_found"] == 2
        assert result["discovery_metadata"]["status"] == "success"

        # Verify sheet structure
        sheet = result["discovered_sheets"][0]
        assert sheet["spreadsheet_id"] == "sheet1"
        assert sheet["title"] == "Campaign Q1 2024"
        assert "Campaign Data" in sheet["sheets"]


class TestFileParser:
    """Test suite for FileParser tool."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Mock(spec=Settings)

    @pytest.fixture
    def mock_auth_manager(self, mock_settings):
        """Mock authenticated GoogleAuthManager."""
        auth_manager = Mock(spec=GoogleAuthManager)
        auth_manager.is_authenticated.return_value = True
        return auth_manager

    @pytest.fixture
    def file_parser(self, mock_auth_manager, mock_settings):
        """Create FileParser with mocked dependencies."""
        return FileParser(auth_manager=mock_auth_manager, settings=mock_settings)

    @pytest.mark.asyncio
    async def test_parse_google_drive_file_spreadsheet(self, file_parser):
        """Test parsing a Google Drive spreadsheet file."""
        file_id = "test_file_id_123"

        # Mock drive client response
        mock_file_info = Mock()
        mock_file_info.name = "Campaign Data.xlsx"
        mock_file_info.mimeType = "application/vnd.google-apps.spreadsheet"
        mock_file_info.id = file_id

        mock_drive_client = Mock(spec=GoogleDriveClient)
        mock_drive_client.get_file_info.return_value = mock_file_info
        mock_drive_client.__enter__.return_value = mock_drive_client
        mock_drive_client.__exit__.return_value = None

        file_parser._drive_client = mock_drive_client

        # Mock sheets reader for spreadsheet parsing
        mock_sheets_data = {
            "spreadsheet_id": file_id,
            "rows": [["Campaign", "Budget"], ["Test Campaign", "10000"]],
            "parsed_campaigns": [],
        }
        mock_sheets_reader = Mock()
        mock_sheets_reader.extract_data = AsyncMock(return_value=mock_sheets_data)
        file_parser._sheets_reader = mock_sheets_reader

        result = await file_parser.parse_google_drive_file(file_id)

        assert result["success"] is True
        assert result["file_info"]["name"] == "Campaign Data.xlsx"
        assert result["file_info"]["type"] == "google_spreadsheet"
        assert result["parsed_data"] == mock_sheets_data

    @pytest.mark.asyncio
    async def test_parse_file_google_sheets_url(self, file_parser):
        """Test parsing a Google Sheets URL."""
        sheets_url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"

        # Mock sheets reader
        mock_sheets_data = {
            "spreadsheet_id": "abc123",
            "rows": [["Campaign", "Budget"]],
            "parsed_campaigns": [],
        }
        mock_sheets_reader = Mock()
        mock_sheets_reader.extract_data = AsyncMock(return_value=mock_sheets_data)
        file_parser._sheets_reader = mock_sheets_reader

        result = await file_parser.parse_file(sheets_url, "auto")

        assert result["success"] is True
        assert result["file_type"] == "google_sheets"
        assert result["spreadsheet_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_parse_file_google_drive_id(self, file_parser):
        """Test parsing a Google Drive file ID."""
        file_id = "1a2b3c4d5e6f7g8h9i0j"

        # Mock parsing success
        mock_result = {
            "success": True,
            "file_info": {"name": "test.xlsx", "type": "spreadsheet"},
            "parsed_data": {"rows": []},
        }
        file_parser.parse_google_drive_file = AsyncMock(return_value=mock_result)

        result = await file_parser.parse_file(file_id, "auto")

        assert result["success"] is True
        assert result["file_type"] == "google_drive"
        file_parser.parse_google_drive_file.assert_called_once_with(file_id)

    def test_url_detection_methods(self, file_parser):
        """Test URL and ID detection methods."""
        # Test Google Drive ID detection
        assert file_parser._is_google_drive_id("1a2b3c4d5e6f7g8h9i0j") is True
        assert file_parser._is_google_drive_id("short") is False

        # Test Google Sheets URL detection
        sheets_url = "https://docs.google.com/spreadsheets/d/abc123/edit"
        assert file_parser._is_google_sheets_url(sheets_url) is True
        assert file_parser._is_google_sheets_url("https://example.com") is False

        # Test spreadsheet ID extraction
        extracted_id = file_parser._extract_spreadsheet_id(sheets_url)
        assert extracted_id == "abc123"


class TestDataValidator:
    """Test suite for DataValidator tool."""

    @pytest.fixture
    def data_validator(self):
        """Create DataValidator instance."""
        return DataValidator()

    @pytest.fixture
    def sample_sheet_data(self):
        """Sample sheet data for validation."""
        return {
            "spreadsheet_id": "test_sheet_123",
            "rows": [
                ["Campaign Name", "Budget", "Platform", "Start Date", "End Date"],
                ["Summer Sale", "50000", "Google Ads", "2024-06-01", "2024-08-31"],
                ["Winter Promo", "75000", "Meta Ads", "2024-12-01", "2024-12-31"],
            ],
            "headers": [
                "Campaign Name",
                "Budget",
                "Platform",
                "Start Date",
                "End Date",
            ],
            "parsed_campaigns": [
                {
                    "campaign_name": "Summer Sale",
                    "budget": 50000.0,
                    "platform": "Google Ads",
                    "start_date": "2024-06-01",
                    "end_date": "2024-08-31",
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_validate_extracted_sheet_data_success(
        self, data_validator, sample_sheet_data
    ):
        """Test validation of well-formed sheet data."""
        result = await data_validator.validate_extracted_sheet_data(sample_sheet_data)

        assert result["is_valid"] is True
        assert result["data_quality_score"] > 0.0
        assert isinstance(result["errors"], list)
        # Check for actual fields returned by the implementation
        assert "errors" in result
        assert "warnings" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_validate_extracted_sheet_data_missing_headers(self, data_validator):
        """Test validation with missing required headers."""
        invalid_data = {
            "spreadsheet_id": "test_sheet_123",
            "rows": [
                ["Name", "Cost"],  # Missing required headers
                ["Campaign 1", "1000"],
            ],
            "headers": ["Name", "Cost"],
            "parsed_campaigns": [],
        }

        result = await data_validator.validate_extracted_sheet_data(invalid_data)

        assert result["is_valid"] is False
        assert result["data_quality_score"] < 0.5
        assert len(result["errors"]) > 0
        assert any(
            "missing required header" in error.lower() for error in result["errors"]
        )

    @pytest.mark.asyncio
    async def test_validate_campaign_data_budget_validation(self, data_validator):
        """Test campaign data validation with budget rules."""
        campaign_data = {
            "campaigns": [
                {
                    "campaign_name": "Test Campaign",
                    "budget": -1000,  # Invalid negative budget
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "platform": "Google Ads",
                }
            ]
        }

        result = await data_validator.validate_campaign_data(campaign_data)

        assert result["is_valid"] is False
        assert any("budget" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_campaign_data_date_validation(self, data_validator):
        """Test campaign data validation with date rules."""
        campaign_data = {
            "campaigns": [
                {
                    "campaign_name": "Test Campaign",
                    "budget": 10000,
                    "start_date": "2024-12-31",  # Start after end
                    "end_date": "2024-01-01",
                    "platform": "Google Ads",
                }
            ]
        }

        result = await data_validator.validate_campaign_data(campaign_data)

        assert result["is_valid"] is False
        assert any("date" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_campaign_data_required_fields(self, data_validator):
        """Test validation of required campaign fields."""
        campaign_data = {
            "campaigns": [
                {
                    "budget": 10000,
                    # Missing campaign_name
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                }
            ]
        }

        result = await data_validator.validate_campaign_data(campaign_data)

        assert result["is_valid"] is False
        assert any("campaign_name" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_data_quality_scoring(self, data_validator, sample_sheet_data):
        """Test data quality scoring algorithm."""
        # Test high quality data
        result = await data_validator.validate_extracted_sheet_data(sample_sheet_data)
        high_quality_score = result["data_quality_score"]

        # Test lower quality data
        low_quality_data = {
            "spreadsheet_id": "test",
            "rows": [["Name"], ["Campaign"]],  # Minimal data
            "headers": ["Name"],
            "parsed_campaigns": [],
        }

        result_low = await data_validator.validate_extracted_sheet_data(
            low_quality_data
        )
        low_quality_score = result_low["data_quality_score"]

        assert high_quality_score > low_quality_score
        assert 0.0 <= low_quality_score <= 1.0
        assert 0.0 <= high_quality_score <= 1.0


class TestWorkspaceManager:
    """Test suite for WorkspaceManager tool."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Mock(spec=Settings)

    @pytest.fixture
    def mock_auth_manager(self, mock_settings):
        """Mock authenticated GoogleAuthManager."""
        auth_manager = Mock(spec=GoogleAuthManager)
        auth_manager.is_authenticated.return_value = True
        return auth_manager

    @pytest.fixture
    def workspace_manager(self, mock_auth_manager, mock_settings):
        """Create WorkspaceManager with mocked dependencies."""
        return WorkspaceManager(auth_manager=mock_auth_manager, settings=mock_settings)

    @pytest.mark.asyncio
    async def test_discover_campaign_files(self, workspace_manager):
        """Test discovering campaign files in workspace."""
        # Mock discovery results
        mock_files = [
            {
                "id": "file1",
                "name": "Campaign Q1 2024.xlsx",
                "file_type": "google_sheets",
                "url": "https://docs.google.com/spreadsheets/d/file1",
            },
            {
                "id": "file2",
                "name": "Media Plan.docx",
                "file_type": "google_docs",
                "url": "https://docs.google.com/document/d/file2",
            },
        ]

        # Mock sheets reader discovery
        mock_sheets_reader = Mock()
        mock_sheets_reader.discover_campaign_sheets = AsyncMock(
            return_value={
                "discovered_sheets": mock_files[:1],  # Only spreadsheets
                "discovery_metadata": {"sheets_found": 1},
            }
        )
        workspace_manager._sheets_reader = mock_sheets_reader

        # Mock drive client discovery
        mock_drive_client = Mock()
        mock_drive_client.search_files = AsyncMock(
            return_value=mock_files[1:]
        )  # Only docs
        mock_drive_client.__enter__.return_value = mock_drive_client
        mock_drive_client.__exit__.return_value = None
        workspace_manager._drive_client = mock_drive_client

        result = await workspace_manager.discover_campaign_files()

        assert len(result["discovered_files"]) >= 1  # At least spreadsheets
        assert result["discovery_metadata"]["status"] == "success"
        assert "total_files" in result["discovery_metadata"]

    @pytest.mark.asyncio
    async def test_validate_workspace(self, workspace_manager):
        """Test workspace validation."""
        discovered_files = [
            {
                "id": "file1",
                "name": "Campaign Data.xlsx",
                "file_type": "google_sheets",
                "url": "https://docs.google.com/spreadsheets/d/file1",
            }
        ]

        # Mock data validator
        mock_data_validator = Mock()
        mock_data_validator.validate_data = AsyncMock(
            return_value={
                "is_valid": True,
                "data_quality_score": 0.85,
                "errors": [],
                "warnings": [],
            }
        )
        workspace_manager._data_validator = mock_data_validator

        result = await workspace_manager.validate_workspace(discovered_files)

        assert result["is_valid"] is True
        assert result["overall_score"] > 0.0
        assert "file_validations" in result
        assert len(result["file_validations"]) == len(discovered_files)

    @pytest.mark.asyncio
    async def test_execute_operation_discovery(self, workspace_manager):
        """Test executing discovery operations."""
        workspace_manager.discover_campaign_files = AsyncMock(
            return_value={
                "discovered_files": [],
                "discovery_metadata": {"status": "success"},
            }
        )

        result = await workspace_manager.execute_operation("discover_files", {})

        assert result["operation"] == "discover_files"
        assert "result" in result
        workspace_manager.discover_campaign_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_operation_validation(self, workspace_manager):
        """Test executing validation operations."""
        test_files = [{"id": "test", "name": "test.xlsx"}]
        workspace_manager.validate_workspace = AsyncMock(
            return_value={"is_valid": True, "overall_score": 0.9}
        )

        result = await workspace_manager.execute_operation(
            "validate_workspace", {"files": test_files}
        )

        assert result["operation"] == "validate_workspace"
        workspace_manager.validate_workspace.assert_called_once_with(test_files)

    @pytest.mark.asyncio
    async def test_execute_operation_unknown(self, workspace_manager):
        """Test handling of unknown operations."""
        with pytest.raises(ValueError, match="Unknown operation"):
            await workspace_manager.execute_operation("unknown_operation", {})


# Integration test placeholder
@pytest.mark.integration
class TestWorkspaceToolsIntegration:
    """Integration tests for workspace tools with real Google APIs."""

    @pytest.mark.skipif(
        True, reason="Integration tests require Google API setup"  # Skip by default
    )
    @pytest.mark.asyncio
    async def test_real_integration(self):
        """Placeholder for real integration tests."""
        pass
