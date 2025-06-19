"""
Test Google API Integration with LangGraph Tools

Tests for the integration between Google API clients and workspace tools.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from app.services.langgraph.tools.workspace_tools import (
    GoogleSheetsReader,
    FileParser,
    DataValidator,
    WorkspaceManager
)
from app.services.google.auth import GoogleAuthManager
from app.services.google.sheets_client import GoogleSheetsClient, CampaignData
from app.services.google.drive_client import GoogleDriveClient, DriveFile
from app.core.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.GOOGLE_CLIENT_SECRETS_FILE = "test_secrets.json"
    settings.GOOGLE_CREDENTIALS_FILE = "test_credentials.json"
    settings.all_google_scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    return settings


@pytest.fixture
def mock_auth_manager():
    """Create mock auth manager for testing."""
    auth_manager = Mock(spec=GoogleAuthManager)
    auth_manager.is_authenticated.return_value = True
    auth_manager.get_valid_credentials.return_value = Mock()
    return auth_manager


@pytest.fixture
def sample_campaign_data():
    """Sample campaign data for testing."""
    return [
        CampaignData(
            campaign_name="Summer Campaign",
            budget=10000.0,
            start_date="2024-06-01",
            end_date="2024-08-31",
            platform="Google Ads",
            targeting={"age_range": "25-54", "locations": ["US"]},
            metrics={"impressions": 100000, "clicks": 5000},
            raw_row=["Summer Campaign", "10000", "Google Ads", "2024-06-01", "2024-08-31"]
        )
    ]


@pytest.fixture
def sample_sheet_data():
    """Sample sheet data structure for testing."""
    return {
        "spreadsheet_id": "test_sheet_id",
        "spreadsheet_title": "Test Campaign Sheet",
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/test_sheet_id",
        "range": "A1:E10",
        "rows": [
            ["Campaign", "Budget", "Platform", "Start Date", "End Date"],
            ["Summer Campaign", "10000", "Google Ads", "2024-06-01", "2024-08-31"]
        ],
        "headers": ["Campaign", "Budget", "Platform", "Start Date", "End Date"],
        "parsed_campaigns": [
            {
                "campaign_name": "Summer Campaign",
                "budget": 10000.0,
                "start_date": "2024-06-01",
                "end_date": "2024-08-31",
                "platform": "Google Ads",
                "targeting": {},
                "metrics": {},
                "raw_row": ["Summer Campaign", "10000", "Google Ads", "2024-06-01", "2024-08-31"]
            }
        ],
        "extraction_metadata": {
            "timestamp": datetime.utcnow().isoformat(),
            "row_count": 2,
            "column_count": 5,
            "campaigns_parsed": 1,
            "status": "success"
        }
    }


class TestGoogleSheetsReader:
    """Test GoogleSheetsReader integration."""
    
    def test_initialization_with_dependencies(self, mock_auth_manager, mock_settings):
        """Test that GoogleSheetsReader initializes with proper dependencies."""
        reader = GoogleSheetsReader(mock_auth_manager, mock_settings)
        
        assert reader.auth_manager == mock_auth_manager
        assert reader.settings == mock_settings
        assert reader.name == "google_sheets_reader"
        assert reader.description == "Reads data from Google Sheets using the Google Sheets API"
    
    def test_initialization_with_defaults(self):
        """Test that GoogleSheetsReader can initialize with default dependencies."""
        with patch('app.services.langgraph.tools.workspace_tools.get_settings') as mock_get_settings, \
             patch('app.services.langgraph.tools.workspace_tools.GoogleAuthManager') as mock_auth_class:
            
            mock_settings = Mock()
            mock_get_settings.return_value = mock_settings
            mock_auth_manager = Mock()
            mock_auth_class.return_value = mock_auth_manager
            
            reader = GoogleSheetsReader()
            
            assert reader.auth_manager == mock_auth_manager
            assert reader.settings == mock_settings
    
    @pytest.mark.asyncio
    async def test_extract_data_success(self, mock_auth_manager, mock_settings, sample_sheet_data):
        """Test successful data extraction from Google Sheets."""
        reader = GoogleSheetsReader(mock_auth_manager, mock_settings)
        
        # Mock the private _sheets_client instead of the property
        with patch.object(reader, '_sheets_client') as mock_sheets_client:
            # Setup mock context manager behavior
            mock_context = MagicMock()
            mock_sheets_client.__enter__ = Mock(return_value=mock_context)
            mock_sheets_client.__exit__ = Mock(return_value=None)
            
            # Setup mock sheet info
            mock_sheet_info = Mock()
            mock_sheet_info.title = "Test Campaign Sheet"
            mock_sheet_info.url = "https://docs.google.com/spreadsheets/d/test_sheet_id"
            mock_context.get_spreadsheet_info.return_value = mock_sheet_info
            
            # Setup mock sheet data
            mock_sheet_data = Mock()
            mock_sheet_data.values = sample_sheet_data["rows"]
            mock_context.read_range.return_value = mock_sheet_data
            
            # Setup mock campaign data
            mock_campaign = Mock()
            mock_campaign.campaign_name = "Summer Campaign"
            mock_campaign.budget = 10000.0
            mock_campaign.start_date = "2024-06-01"
            mock_campaign.end_date = "2024-08-31"
            mock_campaign.platform = "Google Ads"
            mock_campaign.targeting = {}
            mock_campaign.metrics = {}
            mock_campaign.raw_row = ["Summer Campaign", "10000", "Google Ads", "2024-06-01", "2024-08-31"]
            mock_context.parse_campaign_data.return_value = [mock_campaign]
            
            # Execute the test
            result = await reader.extract_data("test_sheet_id", "A1:E10")
            
            # Verify the result
            assert result["spreadsheet_id"] == "test_sheet_id"
            assert result["spreadsheet_title"] == "Test Campaign Sheet"
            assert result["range"] == "A1:E10"
            assert len(result["parsed_campaigns"]) == 1
            assert result["parsed_campaigns"][0]["campaign_name"] == "Summer Campaign"
            assert result["extraction_metadata"]["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_extract_data_authentication_error(self, mock_auth_manager, mock_settings):
        """Test handling of authentication errors."""
        mock_auth_manager.is_authenticated.return_value = False
        reader = GoogleSheetsReader(mock_auth_manager, mock_settings)
        
        with pytest.raises(ValueError, match="Google API authentication required"):
            await reader.extract_data("test_sheet_id", "A1:E10")
    
    @pytest.mark.asyncio
    async def test_extract_data_no_data_found(self, mock_auth_manager, mock_settings):
        """Test handling when no data is found in the sheet."""
        reader = GoogleSheetsReader(mock_auth_manager, mock_settings)
        
        # Mock the private _sheets_client instead of the property
        with patch.object(reader, '_sheets_client') as mock_sheets_client:
            mock_context = MagicMock()
            mock_sheets_client.__enter__ = Mock(return_value=mock_context)
            mock_sheets_client.__exit__ = Mock(return_value=None)
            
            mock_sheet_info = Mock()
            mock_sheet_info.title = "Empty Sheet"
            mock_sheet_info.url = "https://docs.google.com/spreadsheets/d/test_sheet_id"
            mock_context.get_spreadsheet_info.return_value = mock_sheet_info
            
            mock_sheet_data = Mock()
            mock_sheet_data.values = []
            mock_context.read_range.return_value = mock_sheet_data
            
            result = await reader.extract_data("test_sheet_id", "A1:E10")
            
            assert result["extraction_metadata"]["status"] == "no_data_found"
            assert len(result["rows"]) == 0
            assert len(result["headers"]) == 0


class TestDataValidator:
    """Test DataValidator with new data structures."""
    
    def test_initialization(self):
        """Test DataValidator initialization."""
        validator = DataValidator()
        
        assert validator.name == "data_validator"
        assert "campaign_name" in validator.validation_rules["campaign_data"]["required_fields"]
        assert "Google Ads" in validator.validation_rules["campaign_data"]["valid_platforms"]
    
    @pytest.mark.asyncio
    async def test_validate_extracted_sheet_data_success(self, sample_sheet_data):
        """Test validation of successfully extracted sheet data."""
        validator = DataValidator()
        
        result = await validator.validate_extracted_sheet_data(sample_sheet_data)
        
        assert result["is_valid"] is True
        assert result["data_quality_score"] == 1.0
        assert len(result["errors"]) == 0
        assert result["validation_metadata"]["campaigns_validated"] == 1
    
    @pytest.mark.asyncio
    async def test_validate_extracted_sheet_data_extraction_error(self):
        """Test validation of failed extraction data."""
        validator = DataValidator()
        
        error_data = {
            "extraction_metadata": {
                "status": "error",
                "error_message": "Failed to connect to Google Sheets API"
            }
        }
        
        result = await validator.validate_extracted_sheet_data(error_data)
        
        assert result["is_valid"] is False
        assert len(result["errors"]) == 1
        assert "Data extraction failed" in result["errors"][0]
    
    @pytest.mark.asyncio
    async def test_validate_extracted_sheet_data_no_data(self):
        """Test validation when no data was found."""
        validator = DataValidator()
        
        no_data = {
            "extraction_metadata": {
                "status": "no_data_found"
            }
        }
        
        result = await validator.validate_extracted_sheet_data(no_data)
        
        assert result["data_quality_score"] == 0.0
        assert len(result["warnings"]) == 1
        assert "No data found" in result["warnings"][0]


class TestFileParser:
    """Test FileParser integration."""
    
    def test_initialization(self, mock_auth_manager, mock_settings):
        """Test FileParser initialization."""
        parser = FileParser(mock_auth_manager, mock_settings)
        
        assert parser.auth_manager == mock_auth_manager
        assert parser.settings == mock_settings
        assert "sheets" in parser.supported_formats
    
    def test_google_drive_id_detection(self, mock_auth_manager, mock_settings):
        """Test Google Drive ID detection."""
        parser = FileParser(mock_auth_manager, mock_settings)
        
        # Valid Google Drive ID
        assert parser._is_google_drive_id("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") is True
        
        # Invalid formats
        assert parser._is_google_drive_id("short") is False
        assert parser._is_google_drive_id("https://example.com") is False
    
    def test_google_sheets_url_detection(self, mock_auth_manager, mock_settings):
        """Test Google Sheets URL detection."""
        parser = FileParser(mock_auth_manager, mock_settings)
        
        # Valid Google Sheets URL
        sheets_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
        assert parser._is_google_sheets_url(sheets_url) is True
        
        # Invalid URL
        assert parser._is_google_sheets_url("https://example.com") is False
    
    def test_extract_spreadsheet_id(self, mock_auth_manager, mock_settings):
        """Test extracting spreadsheet ID from URL."""
        parser = FileParser(mock_auth_manager, mock_settings)
        
        sheets_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
        expected_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        
        assert parser._extract_spreadsheet_id(sheets_url) == expected_id
        
        # Invalid URL should raise error
        with pytest.raises(ValueError):
            parser._extract_spreadsheet_id("https://example.com")


class TestWorkspaceManager:
    """Test WorkspaceManager integration."""
    
    def test_initialization(self, mock_auth_manager, mock_settings):
        """Test WorkspaceManager initialization."""
        manager = WorkspaceManager(mock_auth_manager, mock_settings)
        
        assert manager.auth_manager == mock_auth_manager
        assert manager.settings == mock_settings
        assert "discover_campaign_files" in manager.supported_operations
        assert "validate_workspace" in manager.supported_operations
    
    @pytest.mark.asyncio
    async def test_discover_campaign_files_success(self, mock_auth_manager, mock_settings):
        """Test successful campaign file discovery."""
        manager = WorkspaceManager(mock_auth_manager, mock_settings)
        
        # Mock the sheets reader discovery
        mock_discovery_result = {
            "discovered_sheets": [
                {
                    "spreadsheet_id": "test_sheet_1",
                    "title": "Campaign Data",
                    "url": "https://docs.google.com/spreadsheets/d/test_sheet_1"
                }
            ]
        }
        
        with patch.object(manager, '_sheets_reader') as mock_sheets_reader, \
             patch.object(manager, '_drive_client') as mock_drive_client:
            
            # Make the async method return a coroutine
            mock_sheets_reader.discover_campaign_sheets = AsyncMock(return_value=mock_discovery_result)
            
            # Setup drive client context manager
            mock_context = MagicMock()
            mock_drive_client.__enter__ = Mock(return_value=mock_context)
            mock_drive_client.__exit__ = Mock(return_value=None)
            
            # Mock campaign files
            mock_file = Mock()
            mock_file.id = "file_1"
            mock_file.name = "Campaign Assets"
            mock_file.mime_type = "application/pdf"
            mock_file.size = 1024
            mock_file.modified_time = datetime.utcnow()
            mock_file.web_view_link = "https://drive.google.com/file/d/file_1"
            
            mock_context.find_campaign_files.return_value = [mock_file]
            
            result = await manager.discover_campaign_files()
            
            assert result["status"] == "completed"
            assert len(result["discovered_spreadsheets"]) == 1
            assert len(result["discovered_files"]) == 1
            assert result["operation_metadata"]["spreadsheets_found"] == 1
    
    @pytest.mark.asyncio
    async def test_discover_campaign_files_authentication_error(self, mock_auth_manager, mock_settings):
        """Test handling of authentication errors in file discovery."""
        mock_auth_manager.is_authenticated.return_value = False
        manager = WorkspaceManager(mock_auth_manager, mock_settings)
        
        with pytest.raises(ValueError, match="Google API authentication required"):
            await manager.discover_campaign_files()


# Integration test for the complete workflow
class TestGoogleAPIIntegrationWorkflow:
    """Test the complete integration workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_simulation(self, mock_auth_manager, mock_settings, sample_sheet_data):
        """Test a complete workflow from discovery to validation."""
        # Initialize all components
        sheets_reader = GoogleSheetsReader(mock_auth_manager, mock_settings)
        validator = DataValidator()
        workspace_manager = WorkspaceManager(mock_auth_manager, mock_settings)
        
        # Mock the Google API calls
        with patch.object(sheets_reader, '_sheets_client') as mock_sheets_client:
            mock_context = MagicMock()
            mock_sheets_client.__enter__ = Mock(return_value=mock_context)
            mock_sheets_client.__exit__ = Mock(return_value=None)
            
            # Setup successful extraction
            mock_sheet_info = Mock()
            mock_sheet_info.title = sample_sheet_data["spreadsheet_title"]
            mock_context.get_spreadsheet_info.return_value = mock_sheet_info
            
            mock_sheet_data = Mock()
            mock_sheet_data.values = sample_sheet_data["rows"]
            mock_context.read_range.return_value = mock_sheet_data
            
            # Setup campaign data
            mock_campaigns = []
            for campaign_dict in sample_sheet_data["parsed_campaigns"]:
                mock_campaign = Mock()
                for key, value in campaign_dict.items():
                    setattr(mock_campaign, key, value)
                mock_campaigns.append(mock_campaign)
            
            mock_context.parse_campaign_data.return_value = mock_campaigns
            
            # Step 1: Extract data
            extracted_data = await sheets_reader.extract_data("test_sheet_id")
            
            # Step 2: Validate data
            validation_result = await validator.validate_extracted_sheet_data(extracted_data)
            
            # Verify the workflow
            assert extracted_data["extraction_metadata"]["status"] == "success"
            assert validation_result["is_valid"] is True
            assert validation_result["data_quality_score"] == 1.0
            assert len(validation_result["validated_fields"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 