"""
Domain Exceptions

Custom exceptions for the media planning domain layer.
These exceptions represent business rule violations and domain-specific errors.
"""

from typing import Any, Dict, Optional


class DomainError(Exception):
    """Base exception for all domain-related errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class InvalidCampaignError(DomainError):
    """Raised when campaign validation fails."""

    def __init__(
        self,
        message: str,
        campaign_id: Optional[str] = None,
        validation_errors: Optional[Dict[str, str]] = None,
    ):
        details = {"campaign_id": campaign_id}
        if validation_errors:
            details["validation_errors"] = validation_errors
        super().__init__(
            message=message, error_code="INVALID_CAMPAIGN", details=details
        )


class BudgetExceededError(DomainError):
    """Raised when budget allocation exceeds available funds."""

    def __init__(
        self,
        message: str,
        available_budget: Optional[float] = None,
        requested_amount: Optional[float] = None,
        budget_id: Optional[str] = None,
    ):
        details = {
            "available_budget": available_budget,
            "requested_amount": requested_amount,
            "budget_id": budget_id,
        }
        super().__init__(
            message=message, error_code="BUDGET_EXCEEDED", details=details
        )


class TenantAccessError(DomainError):
    """Raised when cross-tenant access is attempted."""

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        requested_tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
    ):
        details = {
            "tenant_id": tenant_id,
            "requested_tenant_id": requested_tenant_id,
            "resource_type": resource_type,
        }
        super().__init__(
            message=message, error_code="TENANT_ACCESS_DENIED", details=details
        )


class CurrencyMismatchError(DomainError):
    """Raised when currency operations with different currencies are attempted."""

    def __init__(
        self,
        message: str,
        currency_a: Optional[str] = None,
        currency_b: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        details = {
            "currency_a": currency_a,
            "currency_b": currency_b,
            "operation": operation,
        }
        super().__init__(
            message=message, error_code="CURRENCY_MISMATCH", details=details
        )


class InvalidDateRangeError(DomainError):
    """Raised when date range validation fails."""

    def __init__(
        self,
        message: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        details = {"start_date": start_date, "end_date": end_date}
        super().__init__(
            message=message, error_code="INVALID_DATE_RANGE", details=details
        )


class CampaignStatusError(DomainError):
    """Raised when invalid campaign status transitions are attempted."""

    def __init__(
        self,
        message: str,
        current_status: Optional[str] = None,
        requested_status: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ):
        details = {
            "current_status": current_status,
            "requested_status": requested_status,
            "campaign_id": campaign_id,
        }
        super().__init__(
            message=message, error_code="INVALID_STATUS_TRANSITION", details=details
        )


class InsufficientDataError(DomainError):
    """Raised when insufficient data is available for domain operations."""

    def __init__(
        self,
        message: str,
        required_fields: Optional[list] = None,
        missing_fields: Optional[list] = None,
    ):
        details = {
            "required_fields": required_fields,
            "missing_fields": missing_fields,
        }
        super().__init__(
            message=message, error_code="INSUFFICIENT_DATA", details=details
        )


class OptimizationError(DomainError):
    """Raised when campaign optimization fails."""

    def __init__(
        self,
        message: str,
        optimization_type: Optional[str] = None,
        campaign_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        details = {
            "optimization_type": optimization_type,
            "campaign_id": campaign_id,
            "reason": reason,
        }
        super().__init__(
            message=message, error_code="OPTIMIZATION_FAILED", details=details
        ) 