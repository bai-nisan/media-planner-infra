"""
Domain Events

Events that represent something significant that happened in the domain.
These events enable loose coupling between aggregates and can be used
to trigger side effects, update read models, or integrate with external systems.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from .value_objects import CampaignStatus, Money


class DomainEvent:
    """
    Base class for all domain events.
    
    Contains common properties and behavior for domain events.
    """

    def __init__(
        self,
        event_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_id = event_id or str(uuid4())
        self.tenant_id = tenant_id
        self.occurred_at = occurred_at or datetime.now()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.__class__.__name__,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": self.metadata,
            **self._event_data(),
        }

    def _event_data(self) -> Dict[str, Any]:
        """Override this method to provide event-specific data."""
        return {}

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(event_id={self.event_id}, tenant_id={self.tenant_id})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"


class CampaignCreatedEvent(DomainEvent):
    """
    Event fired when a new campaign is created.
    
    This event can trigger:
    - Setting up campaign tracking
    - Sending notifications to stakeholders
    - Creating default campaign configurations
    """

    def __init__(
        self,
        campaign_id: str,
        campaign_name: str,
        budget_amount: Money,
        tenant_id: str,
        client_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.budget_amount = budget_amount
        self.client_id = client_id

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "budget_amount": str(self.budget_amount),
            "budget_currency": self.budget_amount.currency.value,
            "client_id": self.client_id,
        }


class CampaignStatusChangedEvent(DomainEvent):
    """
    Event fired when a campaign's status changes.
    
    This event can trigger:
    - Status-specific business logic
    - Notifications to users
    - Analytics tracking
    - External system integrations
    """

    def __init__(
        self,
        campaign_id: str,
        campaign_name: str,
        old_status: CampaignStatus,
        new_status: CampaignStatus,
        tenant_id: str,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.old_status = old_status
        self.new_status = new_status
        self.changed_by = changed_by
        self.reason = reason

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "old_status": self.old_status.value,
            "new_status": self.new_status.value,
            "changed_by": self.changed_by,
            "reason": self.reason,
        }


class CampaignActivatedEvent(DomainEvent):
    """
    Event fired when a campaign is activated.
    
    This event can trigger:
    - Starting media buying processes
    - Initializing tracking systems
    - Setting up performance monitoring
    - Sending activation notifications
    """

    def __init__(
        self,
        campaign_id: str,
        campaign_name: str,
        budget_amount: Money,
        tenant_id: str,
        activation_date: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.budget_amount = budget_amount
        self.activation_date = activation_date or datetime.now()

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "budget_amount": str(self.budget_amount),
            "budget_currency": self.budget_amount.currency.value,
            "activation_date": self.activation_date.isoformat(),
        }


class CampaignCompletedEvent(DomainEvent):
    """
    Event fired when a campaign is completed.
    
    This event can trigger:
    - Final performance calculations
    - Generating campaign reports
    - Archiving campaign data
    - Sending completion notifications
    """

    def __init__(
        self,
        campaign_id: str,
        campaign_name: str,
        total_spent: Money,
        performance_metrics: Dict[str, float],
        tenant_id: str,
        completion_date: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.total_spent = total_spent
        self.performance_metrics = performance_metrics
        self.completion_date = completion_date or datetime.now()

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "total_spent": str(self.total_spent),
            "spent_currency": self.total_spent.currency.value,
            "performance_metrics": self.performance_metrics,
            "completion_date": self.completion_date.isoformat(),
        }


class BudgetAllocatedEvent(DomainEvent):
    """
    Event fired when budget is allocated to a media channel.
    
    This event can trigger:
    - Updating channel-specific tracking
    - Notifying media buying teams
    - Setting up channel-specific campaigns
    - Analytics updates
    """

    def __init__(
        self,
        budget_id: str,
        campaign_id: str,
        channel_name: str,
        allocated_amount: Money,
        allocation_percentage: float,
        tenant_id: str,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.budget_id = budget_id
        self.campaign_id = campaign_id
        self.channel_name = channel_name
        self.allocated_amount = allocated_amount
        self.allocation_percentage = allocation_percentage

    def _event_data(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "campaign_id": self.campaign_id,
            "channel_name": self.channel_name,
            "allocated_amount": str(self.allocated_amount),
            "allocation_currency": self.allocated_amount.currency.value,
            "allocation_percentage": self.allocation_percentage,
        }


class BudgetExceededEvent(DomainEvent):
    """
    Event fired when budget spending exceeds the allocated amount.
    
    This event can trigger:
    - Sending alert notifications
    - Pausing campaigns automatically
    - Escalating to managers
    - Logging compliance issues
    """

    def __init__(
        self,
        budget_id: str,
        campaign_id: str,
        budget_limit: Money,
        actual_spending: Money,
        overage_amount: Money,
        tenant_id: str,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.budget_id = budget_id
        self.campaign_id = campaign_id
        self.budget_limit = budget_limit
        self.actual_spending = actual_spending
        self.overage_amount = overage_amount

    def _event_data(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "campaign_id": self.campaign_id,
            "budget_limit": str(self.budget_limit),
            "actual_spending": str(self.actual_spending),
            "overage_amount": str(self.overage_amount),
            "currency": self.budget_limit.currency.value,
            "overage_percentage": float(
                self.overage_amount.amount / self.budget_limit.amount * 100
            ),
        }


class CampaignOptimizedEvent(DomainEvent):
    """
    Event fired when a campaign is optimized.
    
    This event can trigger:
    - Updating optimization tracking
    - Sending optimization reports
    - Logging optimization history
    - Analytics updates
    """

    def __init__(
        self,
        campaign_id: str,
        optimization_type: str,
        optimization_details: Dict[str, Any],
        tenant_id: str,
        performance_improvement: Optional[Dict[str, float]] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.optimization_type = optimization_type
        self.optimization_details = optimization_details
        self.performance_improvement = performance_improvement or {}

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "optimization_type": self.optimization_type,
            "optimization_details": self.optimization_details,
            "performance_improvement": self.performance_improvement,
        }


class ClientCampaignAssociatedEvent(DomainEvent):
    """
    Event fired when a campaign is associated with a client.
    
    This event can trigger:
    - Updating client dashboards
    - Setting up client-specific tracking
    - Sending client notifications
    - Analytics updates
    """

    def __init__(
        self,
        client_id: str,
        client_name: str,
        campaign_id: str,
        campaign_name: str,
        tenant_id: str,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.client_id = client_id
        self.client_name = client_name
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name

    def _event_data(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
        }


class PerformanceMetricUpdatedEvent(DomainEvent):
    """
    Event fired when campaign performance metrics are updated.
    
    This event can trigger:
    - Real-time dashboard updates
    - Performance alerts
    - Optimization recommendations
    - Analytics calculations
    """

    def __init__(
        self,
        campaign_id: str,
        metric_name: str,
        old_value: Optional[float],
        new_value: float,
        tenant_id: str,
        metric_metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(tenant_id=tenant_id, **kwargs)
        self.campaign_id = campaign_id
        self.metric_name = metric_name
        self.old_value = old_value
        self.new_value = new_value
        self.metric_metadata = metric_metadata or {}

    def _event_data(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "metric_name": self.metric_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "metric_metadata": self.metric_metadata,
            "change_amount": self.new_value - (self.old_value or 0),
            "change_percentage": (
                ((self.new_value - (self.old_value or 0)) / (self.old_value or 1)) * 100
                if self.old_value and self.old_value != 0
                else None
            ),
        } 