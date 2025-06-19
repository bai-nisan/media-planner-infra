"""
Domain Repository Interfaces

Abstract repository interfaces that define the contract for data persistence.
These interfaces are implemented by the infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from .entities import Budget, Campaign, Client, MediaChannel
from .value_objects import CampaignStatus, DateRange


class CampaignRepositoryInterface(ABC):
    """
    Repository interface for Campaign aggregate operations.
    
    Defines the contract for campaign persistence with tenant isolation.
    """

    @abstractmethod
    async def save(self, campaign: Campaign) -> Campaign:
        """Save a campaign (create or update)."""
        pass

    @abstractmethod
    async def get_by_id(self, campaign_id: str, tenant_id: str) -> Optional[Campaign]:
        """Get a campaign by ID with tenant validation."""
        pass

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: str,
        status: Optional[CampaignStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Campaign]:
        """List campaigns for a tenant with optional status filtering."""
        pass

    @abstractmethod
    async def list_by_date_range(
        self,
        tenant_id: str,
        date_range: DateRange,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Campaign]:
        """List campaigns within a date range for a tenant."""
        pass

    @abstractmethod
    async def list_active_campaigns(self, tenant_id: str) -> List[Campaign]:
        """Get all active campaigns for a tenant."""
        pass

    @abstractmethod
    async def delete(self, campaign_id: str, tenant_id: str) -> bool:
        """Delete a campaign by ID with tenant validation."""
        pass

    @abstractmethod
    async def exists(self, campaign_id: str, tenant_id: str) -> bool:
        """Check if a campaign exists."""
        pass

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int:
        """Count total campaigns for a tenant."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        tenant_id: str,
        name_pattern: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Campaign]:
        """Search campaigns by name pattern within a tenant."""
        pass


class BudgetRepositoryInterface(ABC):
    """
    Repository interface for Budget aggregate operations.
    
    Defines the contract for budget persistence with tenant isolation.
    """

    @abstractmethod
    async def save(self, budget: Budget) -> Budget:
        """Save a budget (create or update)."""
        pass

    @abstractmethod
    async def get_by_id(self, budget_id: str, tenant_id: str) -> Optional[Budget]:
        """Get a budget by ID with tenant validation."""
        pass

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Budget]:
        """List budgets for a tenant."""
        pass

    @abstractmethod
    async def delete(self, budget_id: str, tenant_id: str) -> bool:
        """Delete a budget by ID with tenant validation."""
        pass

    @abstractmethod
    async def exists(self, budget_id: str, tenant_id: str) -> bool:
        """Check if a budget exists."""
        pass

    @abstractmethod
    async def get_budgets_by_currency(
        self,
        tenant_id: str,
        currency: str,
    ) -> List[Budget]:
        """Get all budgets for a specific currency within a tenant."""
        pass

    @abstractmethod
    async def get_total_budget_amount(self, tenant_id: str, currency: str) -> float:
        """Get total budget amount across all budgets for a tenant and currency."""
        pass


class ClientRepositoryInterface(ABC):
    """
    Repository interface for Client entity operations.
    
    Defines the contract for client persistence with tenant isolation.
    """

    @abstractmethod
    async def save(self, client: Client) -> Client:
        """Save a client (create or update)."""
        pass

    @abstractmethod
    async def get_by_id(self, client_id: str, tenant_id: str) -> Optional[Client]:
        """Get a client by ID with tenant validation."""
        pass

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Client]:
        """List clients for a tenant."""
        pass

    @abstractmethod
    async def delete(self, client_id: str, tenant_id: str) -> bool:
        """Delete a client by ID with tenant validation."""
        pass

    @abstractmethod
    async def exists(self, client_id: str, tenant_id: str) -> bool:
        """Check if a client exists."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        tenant_id: str,
        name_pattern: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Client]:
        """Search clients by name pattern within a tenant."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str, tenant_id: str) -> Optional[Client]:
        """Get a client by email within a tenant."""
        pass

    @abstractmethod
    async def list_by_industry(
        self,
        tenant_id: str,
        industry: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Client]:
        """List clients by industry within a tenant."""
        pass


class MediaChannelRepositoryInterface(ABC):
    """
    Repository interface for MediaChannel entity operations.
    
    Defines the contract for media channel persistence.
    """

    @abstractmethod
    async def save(self, channel: MediaChannel) -> MediaChannel:
        """Save a media channel (create or update)."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[MediaChannel]:
        """Get a media channel by name."""
        pass

    @abstractmethod
    async def list_all(self, include_inactive: bool = False) -> List[MediaChannel]:
        """List all media channels."""
        pass

    @abstractmethod
    async def list_by_type(self, channel_type: str) -> List[MediaChannel]:
        """List media channels by type."""
        pass

    @abstractmethod
    async def delete(self, name: str) -> bool:
        """Delete a media channel by name."""
        pass

    @abstractmethod
    async def exists(self, name: str) -> bool:
        """Check if a media channel exists."""
        pass

    @abstractmethod
    async def activate(self, name: str) -> bool:
        """Activate a media channel."""
        pass

    @abstractmethod
    async def deactivate(self, name: str) -> bool:
        """Deactivate a media channel."""
        pass


class UnitOfWorkInterface(ABC):
    """
    Unit of Work pattern interface for managing transactions.
    
    Ensures that all repository operations within a unit of work
    are committed or rolled back together.
    """

    @abstractmethod
    async def __aenter__(self):
        """Enter the async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit all changes within this unit of work."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes within this unit of work."""
        pass

    @property
    @abstractmethod
    def campaigns(self) -> CampaignRepositoryInterface:
        """Get the campaigns repository."""
        pass

    @property
    @abstractmethod
    def budgets(self) -> BudgetRepositoryInterface:
        """Get the budgets repository."""
        pass

    @property
    @abstractmethod
    def clients(self) -> ClientRepositoryInterface:
        """Get the clients repository."""
        pass

    @property
    @abstractmethod
    def media_channels(self) -> MediaChannelRepositoryInterface:
        """Get the media channels repository."""
        pass 