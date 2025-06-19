"""
Domain Entities

Rich domain entities that encapsulate business logic and maintain invariants.
These are the core business objects that represent the media planning domain.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import uuid4

from .exceptions import (
    BudgetExceededError,
    CampaignStatusError,
    InvalidCampaignError,
    TenantAccessError,
)
from .value_objects import CampaignStatus, Currency, DateRange, Money, Percentage


class MediaChannel:
    """Domain entity representing a media channel for campaign allocation."""

    def __init__(
        self,
        name: str,
        channel_type: str,
        is_active: bool = True,
        metadata: Optional[Dict] = None,
    ):
        self.name = self._validate_name(name)
        self.channel_type = channel_type.lower()
        self.is_active = is_active
        self.metadata = metadata or {}

    def _validate_name(self, name: str) -> str:
        """Validate channel name."""
        if not name or not name.strip():
            raise ValueError("Channel name cannot be empty")
        return name.strip()

    def activate(self):
        """Activate the media channel."""
        self.is_active = True

    def deactivate(self):
        """Deactivate the media channel."""
        self.is_active = False

    def __eq__(self, other) -> bool:
        if not isinstance(other, MediaChannel):
            return False
        return self.name == other.name and self.channel_type == other.channel_type

    def __hash__(self) -> int:
        return hash((self.name, self.channel_type))

    def __str__(self) -> str:
        return f"{self.name} ({self.channel_type})"


class BudgetAllocation:
    """Value object representing budget allocation to a media channel."""

    def __init__(self, channel: MediaChannel, amount: Money, percentage: Percentage):
        self.channel = channel
        self.amount = amount
        self.percentage = percentage

    def __eq__(self, other) -> bool:
        if not isinstance(other, BudgetAllocation):
            return False
        return (
            self.channel == other.channel
            and self.amount == other.amount
            and self.percentage == other.percentage
        )

    def __str__(self) -> str:
        return f"{self.channel.name}: {self.amount} ({self.percentage})"


class Budget:
    """
    Budget aggregate root with allocation management and validation.
    
    Encapsulates business rules around budget allocation and spending limits.
    """

    def __init__(
        self,
        budget_id: str,
        tenant_id: str,
        total_amount: Money,
        currency: Currency,
        name: Optional[str] = None,
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.budget_id = budget_id or str(uuid4())
        self.tenant_id = self._validate_tenant_id(tenant_id)
        self.total_amount = total_amount
        self.currency = currency
        self.name = name or f"Budget {self.budget_id[:8]}"
        self.description = description
        self.created_at = created_at or datetime.now()
        
        # Budget allocations and spending
        self._allocations: List[BudgetAllocation] = []
        self._spent_amount = Money(0, currency)
        self._reserved_amount = Money(0, currency)

    def _validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant ID format."""
        if not tenant_id or not tenant_id.strip():
            raise TenantAccessError("Tenant ID cannot be empty")
        return tenant_id.strip()

    def add_allocation(self, channel: MediaChannel, amount: Money) -> BudgetAllocation:
        """
        Add a budget allocation to a media channel.
        
        Validates that total allocations don't exceed total budget.
        """
        if amount.currency != self.currency:
            raise ValueError(f"Allocation currency {amount.currency} doesn't match budget currency {self.currency}")
        
        # Check if we already have allocation for this channel
        existing_allocation = self.get_allocation_for_channel(channel)
        if existing_allocation:
            raise ValueError(f"Allocation already exists for channel {channel.name}")
        
        # Calculate what would be the new total allocated amount
        current_allocated = self.get_total_allocated()
        new_total_allocated = current_allocated.add(amount)
        
        if new_total_allocated.is_greater_than(self.total_amount):
            raise BudgetExceededError(
                "Budget allocation would exceed total budget",
                available_budget=float(self.get_remaining_budget().amount),
                requested_amount=float(amount.amount),
                budget_id=self.budget_id,
            )
        
        # Calculate percentage
        percentage = Percentage(float(amount.amount) / float(self.total_amount.amount) * 100)
        allocation = BudgetAllocation(channel, amount, percentage)
        self._allocations.append(allocation)
        
        return allocation

    def update_allocation(self, channel: MediaChannel, new_amount: Money) -> BudgetAllocation:
        """Update an existing allocation for a channel."""
        allocation = self.get_allocation_for_channel(channel)
        if not allocation:
            raise ValueError(f"No allocation found for channel {channel.name}")
        
        # Remove old allocation and add new one
        self._allocations.remove(allocation)
        return self.add_allocation(channel, new_amount)

    def remove_allocation(self, channel: MediaChannel) -> bool:
        """Remove allocation for a specific channel."""
        allocation = self.get_allocation_for_channel(channel)
        if allocation:
            self._allocations.remove(allocation)
            return True
        return False

    def get_allocation_for_channel(self, channel: MediaChannel) -> Optional[BudgetAllocation]:
        """Get allocation for a specific channel."""
        for allocation in self._allocations:
            if allocation.channel == channel:
                return allocation
        return None

    def get_all_allocations(self) -> List[BudgetAllocation]:
        """Get all budget allocations."""
        return self._allocations.copy()

    def get_total_allocated(self) -> Money:
        """Get total amount allocated across all channels."""
        if not self._allocations:
            return Money(0, self.currency)
        
        total = Money(0, self.currency)
        for allocation in self._allocations:
            total = total.add(allocation.amount)
        return total

    def get_remaining_budget(self) -> Money:
        """Get remaining unallocated budget."""
        allocated = self.get_total_allocated()
        return self.total_amount.subtract(allocated)

    def record_spending(self, amount: Money, description: str = "") -> None:
        """Record actual spending against the budget."""
        if amount.currency != self.currency:
            raise ValueError(f"Spending currency {amount.currency} doesn't match budget currency {self.currency}")
        
        new_spent_total = self._spent_amount.add(amount)
        if new_spent_total.is_greater_than(self.total_amount):
            raise BudgetExceededError(
                "Spending would exceed total budget",
                available_budget=float(self.total_amount.amount),
                requested_amount=float(new_spent_total.amount),
                budget_id=self.budget_id,
            )
        
        self._spent_amount = new_spent_total

    def get_spent_amount(self) -> Money:
        """Get total amount spent."""
        return self._spent_amount

    def get_utilization_percentage(self) -> Percentage:
        """Get budget utilization as a percentage."""
        if self.total_amount.is_zero():
            return Percentage(0)
        
        utilization = float(self._spent_amount.amount) / float(self.total_amount.amount) * 100
        return Percentage(utilization)

    def is_over_budget(self) -> bool:
        """Check if spending has exceeded the total budget."""
        return self._spent_amount.is_greater_than(self.total_amount)

    def can_allocate(self, amount: Money) -> bool:
        """Check if additional amount can be allocated."""
        try:
            remaining = self.get_remaining_budget()
            return not amount.is_greater_than(remaining)
        except:
            return False

    def __str__(self) -> str:
        return f"Budget {self.name}: {self.total_amount}"

    def __repr__(self) -> str:
        return f"Budget(id='{self.budget_id}', total={self.total_amount}, tenant='{self.tenant_id}')"


class Campaign:
    """
    Campaign aggregate root with rich business logic.
    
    Encapsulates campaign lifecycle, budget management, and business rules.
    """

    def __init__(
        self,
        campaign_id: str,
        tenant_id: str,
        name: str,
        budget: Budget,
        date_range: DateRange,
        status: Optional[CampaignStatus] = None,
        description: Optional[str] = None,
        target_audience: Optional[Dict] = None,
        kpis: Optional[List[Dict]] = None,
        created_at: Optional[datetime] = None,
    ):
        self.campaign_id = campaign_id or str(uuid4())
        self.tenant_id = self._validate_tenant_id(tenant_id)
        self.name = self._validate_name(name)
        self.budget = budget
        self.date_range = date_range
        self.status = status or CampaignStatus(CampaignStatus.DRAFT)
        self.description = description
        self.target_audience = target_audience or {}
        self.kpis = kpis or []
        self.created_at = created_at or datetime.now()
        self.updated_at = self.created_at
        
        # Performance tracking
        self._performance_metrics: Dict[str, float] = {}
        self._optimization_history: List[Dict] = []

    def _validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant ID."""
        if not tenant_id or not tenant_id.strip():
            raise TenantAccessError("Campaign tenant ID cannot be empty")
        return tenant_id.strip()

    def _validate_name(self, name: str) -> str:
        """Validate campaign name."""
        if not name or not name.strip():
            raise InvalidCampaignError("Campaign name cannot be empty")
        
        if len(name.strip()) < 3:
            raise InvalidCampaignError("Campaign name must be at least 3 characters long")
        
        return name.strip()

    def update_name(self, new_name: str) -> None:
        """Update campaign name with validation."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify campaign in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        self.name = self._validate_name(new_name)
        self._mark_updated()

    def update_description(self, description: str) -> None:
        """Update campaign description."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify campaign in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        self.description = description
        self._mark_updated()

    def update_budget(self, new_budget: Budget) -> None:
        """Update campaign budget with validation."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify campaign budget in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        if new_budget.tenant_id != self.tenant_id:
            raise TenantAccessError(
                "Budget tenant must match campaign tenant",
                tenant_id=self.tenant_id,
                requested_tenant_id=new_budget.tenant_id,
                resource_type="budget",
            )
        
        self.budget = new_budget
        self._mark_updated()

    def schedule(self) -> None:
        """Schedule the campaign."""
        self.status = self.status.transition_to(CampaignStatus.SCHEDULED)
        self._mark_updated()

    def activate(self) -> None:
        """Activate the campaign."""
        if not self.date_range.is_current():
            raise CampaignStatusError(
                "Cannot activate campaign outside its date range",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        # Validate that budget has allocations
        if not self.budget.get_all_allocations():
            raise InvalidCampaignError(
                "Cannot activate campaign without budget allocations",
                campaign_id=self.campaign_id,
            )
        
        self.status = self.status.transition_to(CampaignStatus.ACTIVE)
        self._mark_updated()

    def pause(self) -> None:
        """Pause the campaign."""
        self.status = self.status.transition_to(CampaignStatus.PAUSED)
        self._mark_updated()

    def resume(self) -> None:
        """Resume a paused campaign."""
        if self.status.value != CampaignStatus.PAUSED:
            raise CampaignStatusError(
                "Can only resume paused campaigns",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        self.status = self.status.transition_to(CampaignStatus.ACTIVE)
        self._mark_updated()

    def complete(self) -> None:
        """Mark campaign as completed."""
        self.status = self.status.transition_to(CampaignStatus.COMPLETED)
        self._mark_updated()

    def cancel(self) -> None:
        """Cancel the campaign."""
        self.status = self.status.transition_to(CampaignStatus.CANCELLED)
        self._mark_updated()

    def add_channel_allocation(self, channel: MediaChannel, amount: Money) -> BudgetAllocation:
        """Add budget allocation for a media channel."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify allocations in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        allocation = self.budget.add_allocation(channel, amount)
        self._mark_updated()
        return allocation

    def update_channel_allocation(self, channel: MediaChannel, new_amount: Money) -> BudgetAllocation:
        """Update budget allocation for a media channel."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify allocations in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        allocation = self.budget.update_allocation(channel, new_amount)
        self._mark_updated()
        return allocation

    def remove_channel_allocation(self, channel: MediaChannel) -> bool:
        """Remove budget allocation for a media channel."""
        if not self.status.can_be_modified():
            raise CampaignStatusError(
                f"Cannot modify allocations in {self.status.value} status",
                current_status=self.status.value,
                campaign_id=self.campaign_id,
            )
        
        result = self.budget.remove_allocation(channel)
        if result:
            self._mark_updated()
        return result

    def record_performance_metric(self, metric_name: str, value: float) -> None:
        """Record a performance metric for the campaign."""
        self._performance_metrics[metric_name] = value
        self._mark_updated()

    def get_performance_metric(self, metric_name: str) -> Optional[float]:
        """Get a specific performance metric."""
        return self._performance_metrics.get(metric_name)

    def get_all_performance_metrics(self) -> Dict[str, float]:
        """Get all performance metrics."""
        return self._performance_metrics.copy()

    def add_optimization_record(self, optimization_type: str, details: Dict) -> None:
        """Add an optimization record to the campaign history."""
        record = {
            "type": optimization_type,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self._optimization_history.append(record)
        self._mark_updated()

    def get_optimization_history(self) -> List[Dict]:
        """Get the optimization history."""
        return self._optimization_history.copy()

    def is_active(self) -> bool:
        """Check if campaign is currently active."""
        return self.status.is_active() and self.date_range.is_current()

    def is_ready_to_activate(self) -> bool:
        """Check if campaign is ready to be activated."""
        return (
            self.status.value in {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED}
            and bool(self.budget.get_all_allocations())
            and self.date_range.is_current()
        )

    def get_budget_utilization(self) -> Percentage:
        """Get budget utilization percentage."""
        return self.budget.get_utilization_percentage()

    def _mark_updated(self) -> None:
        """Mark the campaign as updated."""
        self.updated_at = datetime.now()

    def ensure_tenant_access(self, requesting_tenant_id: str) -> None:
        """Ensure the requesting tenant has access to this campaign."""
        if self.tenant_id != requesting_tenant_id:
            raise TenantAccessError(
                "Access denied to campaign from different tenant",
                tenant_id=self.tenant_id,
                requested_tenant_id=requesting_tenant_id,
                resource_type="campaign",
            )

    def __str__(self) -> str:
        return f"Campaign {self.name} ({self.status})"

    def __repr__(self) -> str:
        return (
            f"Campaign(id='{self.campaign_id}', name='{self.name}', "
            f"status='{self.status.value}', tenant='{self.tenant_id}')"
        )


class Client:
    """
    Client entity representing a client in the media planning platform.
    
    Manages client information and campaign associations.
    """

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        name: str,
        email: Optional[str] = None,
        company: Optional[str] = None,
        industry: Optional[str] = None,
        metadata: Optional[Dict] = None,
        created_at: Optional[datetime] = None,
    ):
        self.client_id = client_id or str(uuid4())
        self.tenant_id = self._validate_tenant_id(tenant_id)
        self.name = self._validate_name(name)
        self.email = email
        self.company = company
        self.industry = industry
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = self.created_at
        
        self._campaigns: Set[str] = set()  # Campaign IDs

    def _validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant ID."""
        if not tenant_id or not tenant_id.strip():
            raise TenantAccessError("Client tenant ID cannot be empty")
        return tenant_id.strip()

    def _validate_name(self, name: str) -> str:
        """Validate client name."""
        if not name or not name.strip():
            raise ValueError("Client name cannot be empty")
        return name.strip()

    def update_info(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        company: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> None:
        """Update client information."""
        if name is not None:
            self.name = self._validate_name(name)
        if email is not None:
            self.email = email
        if company is not None:
            self.company = company
        if industry is not None:
            self.industry = industry
        
        self.updated_at = datetime.now()

    def add_campaign(self, campaign_id: str) -> None:
        """Associate a campaign with this client."""
        self._campaigns.add(campaign_id)
        self.updated_at = datetime.now()

    def remove_campaign(self, campaign_id: str) -> None:
        """Remove campaign association."""
        self._campaigns.discard(campaign_id)
        self.updated_at = datetime.now()

    def get_campaign_ids(self) -> Set[str]:
        """Get all associated campaign IDs."""
        return self._campaigns.copy()

    def ensure_tenant_access(self, requesting_tenant_id: str) -> None:
        """Ensure the requesting tenant has access to this client."""
        if self.tenant_id != requesting_tenant_id:
            raise TenantAccessError(
                "Access denied to client from different tenant",
                tenant_id=self.tenant_id,
                requested_tenant_id=requesting_tenant_id,
                resource_type="client",
            )

    def __str__(self) -> str:
        company_info = f" ({self.company})" if self.company else ""
        return f"Client {self.name}{company_info}"

    def __repr__(self) -> str:
        return f"Client(id='{self.client_id}', name='{self.name}', tenant='{self.tenant_id}')" 