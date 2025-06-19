"""
Data Extraction and Transformation Workflows

Orchestrates the complete data pipeline for media planning:
- Google Drive file discovery
- Google Sheets data extraction
- Data transformation and validation
- Bidirectional sync mechanisms
- Google Ads performance data integration
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator

from app.core.config import Settings
from app.services.google.ads_client import GoogleAdsClient
from app.services.google.auth import GoogleAuthManager
from app.services.google.drive_client import DriveFile, GoogleDriveClient
from app.services.google.sheets_client import CampaignData, GoogleSheetsClient

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DataSource(str, Enum):
    """Data source types."""

    GOOGLE_DRIVE = "google_drive"
    GOOGLE_SHEETS = "google_sheets"
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"


@dataclass
class WorkflowContext:
    """Context for workflow execution."""

    tenant_id: str
    user_id: str
    workflow_id: str
    started_at: datetime
    settings: Dict[str, Any]


class CampaignFile(BaseModel):
    """Standardized campaign file model."""

    file_id: str
    name: str
    source: DataSource
    file_type: str
    size_bytes: Optional[int] = None
    last_modified: datetime
    url: str
    metadata: Dict[str, Any] = {}


class StandardizedCampaign(BaseModel):
    """Standardized campaign model for internal use."""

    campaign_id: str
    name: str
    platform: str
    budget_total: Optional[float] = None
    budget_daily: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "draft"
    targeting: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    source_file: Optional[str] = None
    source_sheet: Optional[str] = None
    raw_data: Dict[str, Any] = {}

    @validator("budget_total", "budget_daily")
    def validate_budget(cls, v):
        """Ensure budget values are positive."""
        if v is not None and v < 0:
            raise ValueError("Budget must be positive")
        return v


class DataTransformationResult(BaseModel):
    """Result of data transformation operation."""

    success: bool
    campaigns_processed: int
    campaigns_valid: int
    campaigns_invalid: int
    errors: List[str] = []
    warnings: List[str] = []
    transformed_data: List[StandardizedCampaign] = []


class SyncResult(BaseModel):
    """Result of bidirectional sync operation."""

    success: bool
    files_discovered: int
    sheets_processed: int
    campaigns_extracted: int
    campaigns_transformed: int
    sync_direction: str  # "drive_to_internal", "internal_to_sheets", "bidirectional"
    errors: List[str] = []
    execution_time_seconds: float


class DataWorkflowService:
    """
    Main service for orchestrating data extraction and transformation workflows.

    Coordinates between Google Drive, Sheets, and Ads APIs to create a unified
    data pipeline for media planning operations.
    """

    def __init__(self, settings: Settings):
        """Initialize the workflow service."""
        self.settings = settings
        self._auth_manager = None

    @property
    def auth_manager(self) -> GoogleAuthManager:
        """Get or create auth manager."""
        if not self._auth_manager:
            self._auth_manager = GoogleAuthManager(self.settings)
        return self._auth_manager

    @asynccontextmanager
    async def get_clients(self):
        """Context manager to get all required API clients."""
        drive_client = GoogleDriveClient(self.auth_manager, self.settings)
        sheets_client = GoogleSheetsClient(self.auth_manager, self.settings)
        ads_client = GoogleAdsClient(self.auth_manager, self.settings)

        try:
            yield {"drive": drive_client, "sheets": sheets_client, "ads": ads_client}
        finally:
            # Cleanup all clients
            for client in [drive_client, sheets_client, ads_client]:
                try:
                    client.close()
                except Exception as e:
                    logger.warning(f"Error closing client: {e}")

    async def discover_campaign_files(
        self,
        context: WorkflowContext,
        search_keywords: List[str] = None,
        folder_id: Optional[str] = None,
    ) -> List[CampaignFile]:
        """
        Discover campaign-related files in Google Drive.

        Args:
            context: Workflow execution context
            search_keywords: Keywords to search for (e.g., ["campaign", "media plan"])
            folder_id: Specific folder to search in

        Returns:
            List of discovered campaign files
        """
        logger.info(f"Starting file discovery for tenant {context.tenant_id}")

        async with self.get_clients() as clients:
            drive_client = clients["drive"]

            # Default search keywords for campaign files
            if not search_keywords:
                search_keywords = [
                    "campaign",
                    "media plan",
                    "advertising",
                    "marketing",
                    "budget",
                    "performance",
                    "analytics",
                ]

            discovered_files = []

            try:
                # Search for campaign-related files
                drive_files = drive_client.find_campaign_files(
                    campaign_keywords=search_keywords, folder_id=folder_id
                )

                # Convert to standardized format
                for drive_file in drive_files:
                    campaign_file = CampaignFile(
                        file_id=drive_file.id,
                        name=drive_file.name,
                        source=DataSource.GOOGLE_DRIVE,
                        file_type=drive_file.mime_type,
                        size_bytes=drive_file.size,
                        last_modified=drive_file.modified_time,
                        url=drive_file.web_view_link,
                        metadata={
                            "created_time": drive_file.created_time.isoformat(),
                            "parents": drive_file.parents,
                            "shared": drive_file.shared,
                        },
                    )
                    discovered_files.append(campaign_file)

                logger.info(f"Discovered {len(discovered_files)} campaign files")
                return discovered_files

            except Exception as e:
                logger.error(f"File discovery failed: {e}")
                raise

    async def extract_sheets_data(
        self, context: WorkflowContext, spreadsheet_files: List[CampaignFile]
    ) -> List[CampaignData]:
        """
        Extract campaign data from Google Sheets files.

        Args:
            context: Workflow execution context
            spreadsheet_files: List of spreadsheet files to process

        Returns:
            List of extracted campaign data
        """
        logger.info(f"Extracting data from {len(spreadsheet_files)} spreadsheets")

        async with self.get_clients() as clients:
            sheets_client = clients["sheets"]

            all_campaign_data = []

            for file in spreadsheet_files:
                # Only process spreadsheet files
                if "spreadsheet" not in file.file_type.lower():
                    continue

                try:
                    # Extract spreadsheet ID from Drive file ID
                    # (In Google Drive, spreadsheet file ID = spreadsheet ID)
                    spreadsheet_id = file.file_id

                    # Parse campaign data from the spreadsheet
                    campaign_data = sheets_client.parse_campaign_data(
                        spreadsheet_id=spreadsheet_id,
                        sheet_name="Sheet1",  # Default sheet name
                        header_row=1,
                        data_start_row=2,
                    )

                    # Add source file metadata
                    for campaign in campaign_data:
                        campaign.raw_row.append(f"source_file:{file.name}")

                    all_campaign_data.extend(campaign_data)
                    logger.info(
                        f"Extracted {len(campaign_data)} campaigns from {file.name}"
                    )

                except Exception as e:
                    logger.error(f"Failed to extract data from {file.name}: {e}")
                    continue

            logger.info(f"Total campaigns extracted: {len(all_campaign_data)}")
            return all_campaign_data

    async def transform_campaign_data(
        self, context: WorkflowContext, raw_campaign_data: List[CampaignData]
    ) -> DataTransformationResult:
        """
        Transform raw campaign data into standardized internal format.

        Args:
            context: Workflow execution context
            raw_campaign_data: Raw campaign data from various sources

        Returns:
            Transformation result with standardized campaigns
        """
        logger.info(f"Transforming {len(raw_campaign_data)} raw campaigns")

        transformed_campaigns = []
        errors = []
        warnings = []
        invalid_count = 0

        for i, raw_campaign in enumerate(raw_campaign_data):
            try:
                # Create standardized campaign
                standardized = StandardizedCampaign(
                    campaign_id=f"{context.tenant_id}_{i}_{int(datetime.utcnow().timestamp())}",
                    name=raw_campaign.campaign_name,
                    platform=raw_campaign.platform or "unknown",
                    budget_total=raw_campaign.budget,
                    start_date=self._parse_date(raw_campaign.start_date),
                    end_date=self._parse_date(raw_campaign.end_date),
                    targeting=raw_campaign.targeting,
                    metrics=raw_campaign.metrics,
                    raw_data={
                        "source": "google_sheets",
                        "raw_row": raw_campaign.raw_row,
                        "extracted_at": datetime.utcnow().isoformat(),
                    },
                )

                # Validate campaign data
                validation_errors = self._validate_campaign(standardized)
                if validation_errors:
                    warnings.extend(
                        [
                            f"Campaign '{standardized.name}': {err}"
                            for err in validation_errors
                        ]
                    )

                transformed_campaigns.append(standardized)

            except Exception as e:
                error_msg = f"Failed to transform campaign {i}: {e}"
                errors.append(error_msg)
                invalid_count += 1
                logger.error(error_msg)
                continue

        result = DataTransformationResult(
            success=len(errors) == 0,
            campaigns_processed=len(raw_campaign_data),
            campaigns_valid=len(transformed_campaigns),
            campaigns_invalid=invalid_count,
            errors=errors,
            warnings=warnings,
            transformed_data=transformed_campaigns,
        )

        logger.info(
            f"Transformation completed: {result.campaigns_valid}/{result.campaigns_processed} valid"
        )
        return result

    async def sync_data_bidirectional(
        self,
        context: WorkflowContext,
        discover_files: bool = True,
        update_sheets: bool = False,
        folder_id: Optional[str] = None,
    ) -> SyncResult:
        """
        Perform complete bidirectional data synchronization.

        Args:
            context: Workflow execution context
            discover_files: Whether to discover new files
            update_sheets: Whether to write back to sheets
            folder_id: Specific folder to sync

        Returns:
            Sync operation result
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting bidirectional sync for tenant {context.tenant_id}")

        try:
            # Step 1: Discover campaign files
            discovered_files = []
            if discover_files:
                discovered_files = await self.discover_campaign_files(
                    context=context, folder_id=folder_id
                )

            # Step 2: Extract data from spreadsheets
            spreadsheet_files = [
                f for f in discovered_files if "spreadsheet" in f.file_type.lower()
            ]
            raw_campaigns = await self.extract_sheets_data(
                context=context, spreadsheet_files=spreadsheet_files
            )

            # Step 3: Transform data
            transformation_result = await self.transform_campaign_data(
                context=context, raw_campaign_data=raw_campaigns
            )

            # Step 4: Update sheets if requested
            if update_sheets:
                await self._write_back_to_sheets(
                    context=context,
                    campaigns=transformation_result.transformed_data,
                    spreadsheet_files=spreadsheet_files,
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            result = SyncResult(
                success=transformation_result.success,
                files_discovered=len(discovered_files),
                sheets_processed=len(spreadsheet_files),
                campaigns_extracted=len(raw_campaigns),
                campaigns_transformed=transformation_result.campaigns_valid,
                sync_direction=(
                    "bidirectional" if update_sheets else "drive_to_internal"
                ),
                errors=transformation_result.errors,
                execution_time_seconds=execution_time,
            )

            logger.info(
                f"Sync completed in {execution_time:.2f}s: {result.campaigns_transformed} campaigns"
            )
            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Sync failed after {execution_time:.2f}s: {e}")

            return SyncResult(
                success=False,
                files_discovered=0,
                sheets_processed=0,
                campaigns_extracted=0,
                campaigns_transformed=0,
                sync_direction="failed",
                errors=[str(e)],
                execution_time_seconds=execution_time,
            )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string into date object."""
        if not date_str:
            return None

        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.date()
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.warning(f"Date parsing error for '{date_str}': {e}")
            return None

    def _validate_campaign(self, campaign: StandardizedCampaign) -> List[str]:
        """Validate campaign data and return list of issues."""
        issues = []

        if not campaign.name or len(campaign.name.strip()) == 0:
            issues.append("Campaign name is required")

        if campaign.budget_total is not None and campaign.budget_total <= 0:
            issues.append("Budget must be positive")

        if campaign.start_date and campaign.end_date:
            if campaign.start_date > campaign.end_date:
                issues.append("Start date must be before end date")

        return issues

    async def _write_back_to_sheets(
        self,
        context: WorkflowContext,
        campaigns: List[StandardizedCampaign],
        spreadsheet_files: List[CampaignFile],
    ) -> None:
        """Write transformed campaign data back to source sheets."""
        logger.info(f"Writing back {len(campaigns)} campaigns to sheets")

        async with self.get_clients() as clients:
            sheets_client = clients["sheets"]

            # For now, just log the operation
            # In a full implementation, this would update the sheets with new data
            for file in spreadsheet_files:
                relevant_campaigns = [
                    c for c in campaigns if file.name in str(c.raw_data)
                ]
                if relevant_campaigns:
                    logger.info(
                        f"Would update {file.name} with {len(relevant_campaigns)} campaigns"
                    )


# Factory function for dependency injection
def get_data_workflow_service(settings: Settings) -> DataWorkflowService:
    """Factory function to create DataWorkflowService instance."""
    return DataWorkflowService(settings)
