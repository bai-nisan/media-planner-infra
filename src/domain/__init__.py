"""
Domain Layer

The domain layer contains the core business logic and rules.
It is independent of external concerns like databases, frameworks, and UI.
"""

# Value Objects
from .value_objects import (
    Money,
    Currency,
    DateRange,
    CampaignStatus,
    Percentage,
)

# Entities
from .entities import (
    Campaign,
    Budget,
    MediaChannel,
    Client,
    BudgetAllocation,
)

# Repository Interfaces
from .interfaces import (
    CampaignRepositoryInterface,
    BudgetRepositoryInterface,
    ClientRepositoryInterface,
    MediaChannelRepositoryInterface,
    UnitOfWorkInterface,
)

# Domain Services
from .services import (
    BudgetAllocationService,
    CampaignOptimizationService,
    AllocationStrategy,
    OptimizationType,
)

# Domain Events
from .events import (
    DomainEvent,
    CampaignCreatedEvent,
    CampaignStatusChangedEvent,
    CampaignActivatedEvent,
    CampaignCompletedEvent,
    BudgetAllocatedEvent,
    BudgetExceededEvent,
    CampaignOptimizedEvent,
    ClientCampaignAssociatedEvent,
    PerformanceMetricUpdatedEvent,
)

# Domain Exceptions
from .exceptions import (
    DomainError,
    InvalidCampaignError,
    BudgetExceededError,
    TenantAccessError,
    CurrencyMismatchError,
    InvalidDateRangeError,
    CampaignStatusError,
    InsufficientDataError,
    OptimizationError,
)

__all__ = [
    # Value Objects
    "Money",
    "Currency", 
    "DateRange",
    "CampaignStatus",
    "Percentage",
    # Entities
    "Campaign",
    "Budget",
    "MediaChannel",
    "Client",
    "BudgetAllocation",
    # Repository Interfaces
    "CampaignRepositoryInterface",
    "BudgetRepositoryInterface",
    "ClientRepositoryInterface",
    "MediaChannelRepositoryInterface",
    "UnitOfWorkInterface",
    # Domain Services
    "BudgetAllocationService",
    "CampaignOptimizationService",
    "AllocationStrategy",
    "OptimizationType",
    # Domain Events
    "DomainEvent",
    "CampaignCreatedEvent",
    "CampaignStatusChangedEvent",
    "CampaignActivatedEvent",
    "CampaignCompletedEvent",
    "BudgetAllocatedEvent",
    "BudgetExceededEvent",
    "CampaignOptimizedEvent",
    "ClientCampaignAssociatedEvent",
    "PerformanceMetricUpdatedEvent",
    # Domain Exceptions
    "DomainError",
    "InvalidCampaignError",
    "BudgetExceededError",
    "TenantAccessError",
    "CurrencyMismatchError",
    "InvalidDateRangeError",
    "CampaignStatusError",
    "InsufficientDataError",
    "OptimizationError",
]
