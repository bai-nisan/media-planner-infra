"""
Command DTOs for write operations in the Media Planning Platform.

Data Transfer Objects that represent commands for state-changing operations
following CQRS pattern principles.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class CreateCampaignCommand(BaseModel):
    """Command to create a new campaign."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    description: Optional[str] = Field(None, max_length=1000, description="Campaign description")
    
    # Budget information
    budget_amount: Decimal = Field(..., gt=0, description="Total budget amount")
    budget_currency: str = Field(default="USD", description="Budget currency code")
    
    # Campaign timeline
    start_date: datetime = Field(..., description="Campaign start date")
    end_date: datetime = Field(..., description="Campaign end date")
    
    # Client association
    client_id: Optional[UUID] = Field(None, description="Associated client ID")
    
    # Metadata and tags
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional campaign metadata")
    tags: Optional[List[str]] = Field(default_factory=list, description="Campaign tags")
    
    # Multi-tenancy
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    created_by: str = Field(..., description="User who created the campaign")

    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        """Ensure end date is after start date."""
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

    @validator('budget_currency')
    def validate_currency(cls, v):
        """Validate currency code format."""
        if len(v) != 3 or not v.isupper():
            raise ValueError('Currency must be a 3-letter uppercase code')
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "Summer Product Launch",
                "description": "Campaign for new product launch targeting millennials",
                "budget_amount": "50000.00",
                "budget_currency": "USD",
                "start_date": "2024-06-01T00:00:00Z",
                "end_date": "2024-08-31T23:59:59Z",
                "client_id": "123e4567-e89b-12d3-a456-426614174000",
                "metadata": {"target_audience": "millennials", "product": "new_launch"},
                "tags": ["summer", "product_launch", "millennials"],
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_by": "user@example.com"
            }
        }


class UpdateCampaignCommand(BaseModel):
    """Command to update an existing campaign."""
    
    campaign_id: UUID = Field(..., description="Campaign ID to update")
    
    # Optional fields for updates
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    budget_amount: Optional[Decimal] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Optional[Dict] = None
    tags: Optional[List[str]] = None
    
    # Audit information
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    updated_by: str = Field(..., description="User who updated the campaign")

    @validator('end_date')
    def end_date_validation(cls, v, values):
        """Validate end date if both start and end dates are provided."""
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            if v <= values['start_date']:
                raise ValueError('End date must be after start date')
        return v


class AllocateBudgetCommand(BaseModel):
    """Command to allocate budget to media channels."""
    
    campaign_id: UUID = Field(..., description="Campaign ID for budget allocation")
    budget_id: UUID = Field(..., description="Budget ID to allocate from")
    
    # Allocation details
    allocations: List[Dict[str, Decimal]] = Field(
        ..., 
        description="Channel allocations as {channel_name: amount}",
        min_items=1
    )
    
    # Allocation strategy
    strategy: str = Field(
        default="manual",
        description="Allocation strategy used"
    )
    
    # Multi-tenancy and audit
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    allocated_by: str = Field(..., description="User who performed allocation")

    @validator('allocations')
    def validate_allocations(cls, v):
        """Ensure all allocation amounts are positive."""
        for allocation in v:
            for channel_name, amount in allocation.items():
                if amount <= 0:
                    raise ValueError(f'Allocation amount for {channel_name} must be positive')
        return v

    @validator('strategy')
    def validate_strategy(cls, v):
        """Validate allocation strategy."""
        valid_strategies = ['manual', 'equal_split', 'performance_weighted', 'cost_efficiency', 'reach_weighted']
        if v not in valid_strategies:
            raise ValueError(f'Strategy must be one of: {", ".join(valid_strategies)}')
        return v


class ActivateCampaignCommand(BaseModel):
    """Command to activate a campaign."""
    
    campaign_id: UUID = Field(..., description="Campaign ID to activate")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    activated_by: str = Field(..., description="User who activated the campaign")


class PauseCampaignCommand(BaseModel):
    """Command to pause a campaign."""
    
    campaign_id: UUID = Field(..., description="Campaign ID to pause")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for pausing")
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    paused_by: str = Field(..., description="User who paused the campaign")


class CreateClientCommand(BaseModel):
    """Command to create a new client."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Client name")
    email: str = Field(..., description="Client email address")
    
    # Optional client information
    industry: Optional[str] = Field(None, max_length=100, description="Client industry")
    company_size: Optional[str] = Field(None, max_length=50, description="Company size")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    website: Optional[str] = Field(None, max_length=255, description="Website URL")
    address: Optional[str] = Field(None, max_length=1000, description="Address")
    description: Optional[str] = Field(None, max_length=1000, description="Client description")
    
    # Flexible data storage
    additional_info: Optional[Dict] = Field(default_factory=dict, description="Additional client information")
    interests: Optional[List[str]] = Field(default_factory=list, description="Client interests/preferences")
    
    # Multi-tenancy and audit
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    created_by: str = Field(..., description="User who created the client")

    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower()

    @validator('website')
    def validate_website(cls, v):
        """Basic website URL validation."""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            return f'https://{v}'
        return v


class UpdateClientCommand(BaseModel):
    """Command to update an existing client."""
    
    client_id: UUID = Field(..., description="Client ID to update")
    
    # Optional fields for updates
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=1000)
    description: Optional[str] = Field(None, max_length=1000)
    additional_info: Optional[Dict] = None
    interests: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    # Multi-tenancy and audit
    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    updated_by: str = Field(..., description="User who updated the client")

    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and ('@' not in v or '.' not in v.split('@')[-1]):
            raise ValueError('Invalid email format')
        return v.lower() if v else v 