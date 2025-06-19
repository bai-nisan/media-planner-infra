"""
Query DTOs for read operations in the Media Planning Platform.

Data Transfer Objects that represent queries for data retrieval operations
following CQRS pattern principles.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class GetCampaignQuery(BaseModel):
    """Query to get a specific campaign by ID."""
    
    campaign_id: UUID = Field(..., description="Campaign ID to retrieve")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    include_allocations: bool = Field(default=False, description="Include budget allocations")
    include_performance: bool = Field(default=False, description="Include performance metrics")


class ListCampaignsQuery(BaseModel):
    """Query to list campaigns with filtering and pagination."""
    
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Filtering
    status: Optional[str] = Field(None, description="Filter by campaign status")
    client_id: Optional[UUID] = Field(None, description="Filter by client ID")
    start_date_from: Optional[datetime] = Field(None, description="Filter campaigns starting from date")
    start_date_to: Optional[datetime] = Field(None, description="Filter campaigns starting to date")
    budget_min: Optional[Decimal] = Field(None, ge=0, description="Minimum budget amount")
    budget_max: Optional[Decimal] = Field(None, ge=0, description="Maximum budget amount")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (any match)")
    
    # Search
    search: Optional[str] = Field(None, max_length=100, description="Search in campaign name/description")
    
    # Sorting
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")

    @validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field."""
        valid_fields = ['name', 'created_at', 'start_date', 'end_date', 'budget_amount', 'status']
        if v not in valid_fields:
            raise ValueError(f'Sort field must be one of: {", ".join(valid_fields)}')
        return v

    @validator('sort_order')
    def validate_sort_order(cls, v):
        """Validate sort order."""
        if v.lower() not in ['asc', 'desc']:
            raise ValueError('Sort order must be "asc" or "desc"')
        return v.lower()


class GetCampaignMetricsQuery(BaseModel):
    """Query to get campaign performance metrics."""
    
    campaign_id: UUID = Field(..., description="Campaign ID for metrics")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Time range for metrics
    date_from: Optional[datetime] = Field(None, description="Metrics from date")
    date_to: Optional[datetime] = Field(None, description="Metrics to date")
    
    # Grouping options
    group_by: Optional[str] = Field(None, description="Group metrics by (day, week, month, channel)")
    
    # Specific metrics to include
    include_spend: bool = Field(default=True, description="Include spend metrics")
    include_impressions: bool = Field(default=True, description="Include impression metrics") 
    include_clicks: bool = Field(default=True, description="Include click metrics")
    include_conversions: bool = Field(default=True, description="Include conversion metrics")

    @validator('group_by')
    def validate_group_by(cls, v):
        """Validate grouping option."""
        if v and v not in ['day', 'week', 'month', 'channel']:
            raise ValueError('Group by must be one of: day, week, month, channel')
        return v


class GetClientQuery(BaseModel):
    """Query to get a specific client by ID."""
    
    client_id: UUID = Field(..., description="Client ID to retrieve")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    include_campaigns: bool = Field(default=False, description="Include associated campaigns")


class ListClientsQuery(BaseModel):
    """Query to list clients with filtering and pagination."""
    
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Filtering
    industry: Optional[str] = Field(None, description="Filter by industry")
    company_size: Optional[str] = Field(None, description="Filter by company size")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    interests: Optional[List[str]] = Field(None, description="Filter by interests (any match)")
    
    # Search
    search: Optional[str] = Field(None, max_length=100, description="Search in client name/email")
    
    # Sorting
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")

    @validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field."""
        valid_fields = ['name', 'email', 'industry', 'created_at', 'updated_at']
        if v not in valid_fields:
            raise ValueError(f'Sort field must be one of: {", ".join(valid_fields)}')
        return v

    @validator('sort_order')
    def validate_sort_order(cls, v):
        """Validate sort order."""
        if v.lower() not in ['asc', 'desc']:
            raise ValueError('Sort order must be "asc" or "desc"')
        return v.lower()


class GetBudgetQuery(BaseModel):
    """Query to get budget information."""
    
    budget_id: UUID = Field(..., description="Budget ID to retrieve")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    include_allocations: bool = Field(default=True, description="Include budget allocations")


class ListBudgetAllocationsQuery(BaseModel):
    """Query to list budget allocations with filtering."""
    
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Filtering options
    campaign_id: Optional[UUID] = Field(None, description="Filter by campaign ID")
    budget_id: Optional[UUID] = Field(None, description="Filter by budget ID")
    media_channel: Optional[str] = Field(None, description="Filter by media channel")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=200, description="Items per page")
    
    # Include additional data
    include_performance: bool = Field(default=False, description="Include performance data")


class ListMediaChannelsQuery(BaseModel):
    """Query to list available media channels."""
    
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (for tenant-specific channels)")
    
    # Filtering
    channel_type: Optional[str] = Field(None, description="Filter by channel type")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    supports_video: Optional[bool] = Field(None, description="Filter by video support")
    supports_image: Optional[bool] = Field(None, description="Filter by image support")
    supports_text: Optional[bool] = Field(None, description="Filter by text support")
    
    # Cost filtering
    max_cost_per_click: Optional[Decimal] = Field(None, ge=0, description="Maximum cost per click")
    min_minimum_spend: Optional[Decimal] = Field(None, ge=0, description="Minimum spend threshold")
    
    # Targeting capabilities
    geographic_targeting: Optional[bool] = Field(None, description="Filter by geographic targeting")
    demographic_targeting: Optional[bool] = Field(None, description="Filter by demographic targeting")
    
    # Search and sorting
    search: Optional[str] = Field(None, max_length=100, description="Search in channel name/description")
    sort_by: str = Field(default="name", description="Sort field")
    sort_order: str = Field(default="asc", description="Sort order")

    @validator('channel_type')
    def validate_channel_type(cls, v):
        """Validate channel type."""
        if v:
            valid_types = ['social', 'search', 'display', 'video', 'email', 'print', 'radio', 'tv', 'outdoor']
            if v not in valid_types:
                raise ValueError(f'Channel type must be one of: {", ".join(valid_types)}')
        return v

    @validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field."""
        valid_fields = ['name', 'display_name', 'channel_type', 'cost_per_click', 'minimum_spend', 'created_at']
        if v not in valid_fields:
            raise ValueError(f'Sort field must be one of: {", ".join(valid_fields)}')
        return v


class GenerateReportQuery(BaseModel):
    """Query to generate various types of reports."""
    
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Report configuration
    report_type: str = Field(..., description="Type of report to generate")
    
    # Time range
    date_from: datetime = Field(..., description="Report start date")
    date_to: datetime = Field(..., description="Report end date")
    
    # Filtering options
    campaign_ids: Optional[List[UUID]] = Field(None, description="Specific campaigns to include")
    client_ids: Optional[List[UUID]] = Field(None, description="Specific clients to include")
    channel_names: Optional[List[str]] = Field(None, description="Specific channels to include")
    
    # Report format options
    format: str = Field(default="json", description="Report format (json, csv, pdf)")
    include_charts: bool = Field(default=False, description="Include chart data")
    include_raw_data: bool = Field(default=False, description="Include raw data")

    @validator('report_type')
    def validate_report_type(cls, v):
        """Validate report type."""
        valid_types = [
            'campaign_performance', 'budget_utilization', 'channel_analysis', 
            'client_overview', 'spend_analysis', 'conversion_funnel'
        ]
        if v not in valid_types:
            raise ValueError(f'Report type must be one of: {", ".join(valid_types)}')
        return v

    @validator('format')
    def validate_format(cls, v):
        """Validate report format."""
        if v not in ['json', 'csv', 'pdf']:
            raise ValueError('Format must be one of: json, csv, pdf')
        return v

    @validator('date_to')
    def validate_date_range(cls, v, values):
        """Ensure end date is after start date."""
        if 'date_from' in values and v <= values['date_from']:
            raise ValueError('End date must be after start date')
        return v


class SearchQuery(BaseModel):
    """Generic search query across multiple entities."""
    
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    
    # Search parameters
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    entities: List[str] = Field(default=['campaigns', 'clients'], description="Entities to search")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=50, description="Items per page")
    
    # Search options
    fuzzy_matching: bool = Field(default=True, description="Enable fuzzy matching")
    highlight_matches: bool = Field(default=False, description="Highlight search matches")

    @validator('entities')
    def validate_entities(cls, v):
        """Validate searchable entities."""
        valid_entities = ['campaigns', 'clients', 'media_channels']
        for entity in v:
            if entity not in valid_entities:
                raise ValueError(f'Entity must be one of: {", ".join(valid_entities)}')
        return v 