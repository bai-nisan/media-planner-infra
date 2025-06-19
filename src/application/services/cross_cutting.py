"""
Cross-cutting concern services for the Media Planning Platform.

Provides infrastructure services for logging, validation, authorization,
and other cross-cutting concerns used throughout the application layer.
"""

import logging
import time
import json
from typing import Any, Dict, List, Optional, Callable, Union
from uuid import UUID
from datetime import datetime
from functools import wraps
from enum import Enum

from src.domain.exceptions import DomainError, TenantAccessError


class LogLevel(str, Enum):
    """Application log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEvent(str, Enum):
    """Types of audit events."""
    CAMPAIGN_CREATED = "campaign_created"
    CAMPAIGN_UPDATED = "campaign_updated"
    CAMPAIGN_ACTIVATED = "campaign_activated"
    CAMPAIGN_PAUSED = "campaign_paused"
    BUDGET_ALLOCATED = "budget_allocated"
    CLIENT_CREATED = "client_created"
    CLIENT_UPDATED = "client_updated"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"


class ApplicationLogger:
    """
    Structured logging service for application layer operations.
    
    Provides consistent logging format with audit trail capabilities
    and performance monitoring.
    """
    
    def __init__(self, logger_name: str = "media_planner_app"):
        self.logger = logging.getLogger(logger_name)
        self._configure_logger()

    def _configure_logger(self):
        """Configure structured logging format."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_operation(
        self,
        operation: str,
        tenant_id: UUID,
        user_id: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs
    ) -> None:
        """
        Log application operation with structured data.
        
        Args:
            operation: Operation being performed
            tenant_id: Tenant context
            user_id: User performing operation
            level: Log level
            **kwargs: Additional structured data
        """
        log_data = {
            "operation": operation,
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        message = f"Operation: {operation} | Tenant: {tenant_id} | User: {user_id}"
        if kwargs:
            message += f" | Data: {json.dumps(kwargs, default=str)}"
        
        getattr(self.logger, level.lower())(message)

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        tenant_id: UUID,
        success: bool = True,
        **kwargs
    ) -> None:
        """Log performance metrics for operations."""
        performance_data = {
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "tenant_id": str(tenant_id),
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        level = LogLevel.INFO if success else LogLevel.WARNING
        message = f"Performance: {operation} | Duration: {duration_ms}ms | Success: {success}"
        
        if duration_ms > 1000:  # Log slow operations as warnings
            level = LogLevel.WARNING
            message += " | SLOW_OPERATION"
        
        getattr(self.logger, level.lower())(message)

    def log_audit_event(
        self,
        event: AuditEvent,
        tenant_id: UUID,
        user_id: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit events for security and compliance.
        
        Args:
            event: Type of audit event
            tenant_id: Tenant context
            user_id: User performing action
            resource_id: ID of resource being acted upon
            details: Additional audit details
        """
        audit_data = {
            "audit_event": event.value,
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "resource_id": resource_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        message = f"AUDIT: {event.value} | Tenant: {tenant_id} | User: {user_id}"
        if resource_id:
            message += f" | Resource: {resource_id}"
        
        # All audit events are logged as INFO level for compliance
        self.logger.info(message)

    def log_error(
        self,
        error: Exception,
        operation: str,
        tenant_id: UUID,
        user_id: str,
        **kwargs
    ) -> None:
        """Log application errors with context."""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "operation": operation,
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        message = f"ERROR: {operation} | {type(error).__name__}: {str(error)}"
        self.logger.error(message)


class ValidationService:
    """
    Application-level validation service.
    
    Provides validation logic that spans multiple domain entities
    and enforces business rules at the application layer.
    """
    
    def __init__(self, logger: ApplicationLogger):
        self.logger = logger

    def validate_tenant_access(
        self,
        user_tenant_id: UUID,
        resource_tenant_id: UUID,
        operation: str,
        user_id: str
    ) -> None:
        """
        Validate that user has access to tenant resources.
        
        Args:
            user_tenant_id: User's tenant context
            resource_tenant_id: Resource's tenant context
            operation: Operation being performed
            user_id: User performing operation
            
        Raises:
            TenantAccessError: If access is denied
        """
        if user_tenant_id != resource_tenant_id:
            self.logger.log_audit_event(
                AuditEvent.UNAUTHORIZED_ACCESS,
                user_tenant_id,
                user_id,
                details={
                    "operation": operation,
                    "attempted_tenant": str(resource_tenant_id),
                    "user_tenant": str(user_tenant_id)
                }
            )
            
            raise TenantAccessError(
                f"Access denied: User tenant {user_tenant_id} cannot access "
                f"resources from tenant {resource_tenant_id}",
                tenant_id=user_tenant_id,
                resource_id=str(resource_tenant_id)
            )

    def validate_campaign_budget_allocation(
        self,
        total_budget: float,
        allocations: List[Dict[str, float]],
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        Validate that budget allocations don't exceed total budget.
        
        Args:
            total_budget: Total available budget
            allocations: List of channel allocations
            tolerance: Allowable variance in allocation totals
            
        Returns:
            Validation result with details
            
        Raises:
            DomainError: If validation fails
        """
        total_allocated = 0.0
        channel_allocations = {}
        
        for allocation in allocations:
            for channel, amount in allocation.items():
                if amount < 0:
                    raise DomainError(
                        f"Negative allocation amount for channel {channel}: {amount}"
                    )
                
                if channel in channel_allocations:
                    channel_allocations[channel] += amount
                else:
                    channel_allocations[channel] = amount
                
                total_allocated += amount
        
        # Check if total allocation exceeds budget
        if total_allocated > total_budget + tolerance:
            raise DomainError(
                f"Total allocation ({total_allocated}) exceeds available budget "
                f"({total_budget}) by {total_allocated - total_budget}"
            )
        
        return {
            "is_valid": True,
            "total_budget": total_budget,
            "total_allocated": total_allocated,
            "remaining_budget": total_budget - total_allocated,
            "channel_breakdown": channel_allocations,
            "utilization_percentage": (total_allocated / total_budget) * 100
        }

    def validate_campaign_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        min_duration_days: int = 1,
        max_duration_days: int = 365
    ) -> Dict[str, Any]:
        """
        Validate campaign date range for business rules.
        
        Args:
            start_date: Campaign start date
            end_date: Campaign end date
            min_duration_days: Minimum campaign duration
            max_duration_days: Maximum campaign duration
            
        Returns:
            Validation result with details
            
        Raises:
            DomainError: If validation fails
        """
        now = datetime.utcnow()
        duration = end_date - start_date
        duration_days = duration.days
        
        # Check basic date logic
        if start_date >= end_date:
            raise DomainError("Campaign start date must be before end date")
        
        # Check minimum duration
        if duration_days < min_duration_days:
            raise DomainError(
                f"Campaign duration ({duration_days} days) is below minimum "
                f"of {min_duration_days} days"
            )
        
        # Check maximum duration
        if duration_days > max_duration_days:
            raise DomainError(
                f"Campaign duration ({duration_days} days) exceeds maximum "
                f"of {max_duration_days} days"
            )
        
        # Check if start date is too far in the past
        if start_date < now and (now - start_date).days > 7:
            raise DomainError(
                "Campaign start date cannot be more than 7 days in the past"
            )
        
        return {
            "is_valid": True,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "duration_days": duration_days,
            "is_future_campaign": start_date > now,
            "is_active_period": start_date <= now <= end_date
        }


class AuthorizationService:
    """
    Application-level authorization service.
    
    Manages user permissions and role-based access control
    for application operations.
    """
    
    def __init__(self, logger: ApplicationLogger):
        self.logger = logger

    def check_campaign_permissions(
        self,
        user_id: str,
        tenant_id: UUID,
        campaign_id: UUID,
        operation: str,
        user_roles: List[str] = None
    ) -> bool:
        """
        Check if user has permission to perform campaign operation.
        
        Args:
            user_id: User performing operation
            tenant_id: Tenant context
            campaign_id: Campaign being accessed
            operation: Operation being performed
            user_roles: User's roles in the system
            
        Returns:
            True if authorized, False otherwise
        """
        user_roles = user_roles or []
        
        # Define role-based permissions
        permissions = {
            "create_campaign": ["admin", "campaign_manager", "editor"],
            "update_campaign": ["admin", "campaign_manager", "editor"],
            "delete_campaign": ["admin", "campaign_manager"],
            "view_campaign": ["admin", "campaign_manager", "editor", "viewer"],
            "activate_campaign": ["admin", "campaign_manager"],
            "allocate_budget": ["admin", "campaign_manager"],
            "view_metrics": ["admin", "campaign_manager", "editor", "viewer"]
        }
        
        required_roles = permissions.get(operation, ["admin"])
        has_permission = any(role in required_roles for role in user_roles)
        
        if not has_permission:
            self.logger.log_audit_event(
                AuditEvent.UNAUTHORIZED_ACCESS,
                tenant_id,
                user_id,
                str(campaign_id),
                {
                    "operation": operation,
                    "user_roles": user_roles,
                    "required_roles": required_roles
                }
            )
        
        return has_permission

    def check_client_permissions(
        self,
        user_id: str,
        tenant_id: UUID,
        client_id: UUID,
        operation: str,
        user_roles: List[str] = None
    ) -> bool:
        """
        Check if user has permission to perform client operation.
        
        Args:
            user_id: User performing operation
            tenant_id: Tenant context
            client_id: Client being accessed
            operation: Operation being performed
            user_roles: User's roles in the system
            
        Returns:
            True if authorized, False otherwise
        """
        user_roles = user_roles or []
        
        # Define role-based permissions for client operations
        permissions = {
            "create_client": ["admin", "client_manager", "campaign_manager"],
            "update_client": ["admin", "client_manager", "campaign_manager"],
            "delete_client": ["admin", "client_manager"],
            "view_client": ["admin", "client_manager", "campaign_manager", "editor", "viewer"],
            "manage_client_campaigns": ["admin", "client_manager", "campaign_manager"]
        }
        
        required_roles = permissions.get(operation, ["admin"])
        has_permission = any(role in required_roles for role in user_roles)
        
        if not has_permission:
            self.logger.log_audit_event(
                AuditEvent.UNAUTHORIZED_ACCESS,
                tenant_id,
                user_id,
                str(client_id),
                {
                    "operation": operation,
                    "user_roles": user_roles,
                    "required_roles": required_roles
                }
            )
        
        return has_permission


def performance_monitor(logger: ApplicationLogger):
    """
    Decorator for monitoring operation performance.
    
    Automatically logs operation duration and success/failure.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_name = f"{func.__module__}.{func.__name__}"
            
            # Extract tenant_id from arguments for logging
            tenant_id = None
            for arg in args + tuple(kwargs.values()):
                if hasattr(arg, 'tenant_id'):
                    tenant_id = arg.tenant_id
                    break
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance(
                    operation_name,
                    duration_ms,
                    tenant_id or UUID('00000000-0000-0000-0000-000000000000'),
                    success=True
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance(
                    operation_name,
                    duration_ms,
                    tenant_id or UUID('00000000-0000-0000-0000-000000000000'),
                    success=False,
                    error=str(e)
                )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_name = f"{func.__module__}.{func.__name__}"
            
            # Extract tenant_id from arguments for logging
            tenant_id = None
            for arg in args + tuple(kwargs.values()):
                if hasattr(arg, 'tenant_id'):
                    tenant_id = arg.tenant_id
                    break
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance(
                    operation_name,
                    duration_ms,
                    tenant_id or UUID('00000000-0000-0000-0000-000000000000'),
                    success=True
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance(
                    operation_name,
                    duration_ms,
                    tenant_id or UUID('00000000-0000-0000-0000-000000000000'),
                    success=False,
                    error=str(e)
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    
    return decorator


def audit_operation(
    event: AuditEvent,
    logger: ApplicationLogger,
    extract_resource_id: Callable[[Any], str] = None
):
    """
    Decorator for auditing operations.
    
    Automatically logs audit events for operations.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract audit information from arguments
            tenant_id = None
            user_id = None
            resource_id = None
            
            for arg in args + tuple(kwargs.values()):
                if hasattr(arg, 'tenant_id') and tenant_id is None:
                    tenant_id = arg.tenant_id
                if hasattr(arg, 'created_by') and user_id is None:
                    user_id = arg.created_by
                elif hasattr(arg, 'updated_by') and user_id is None:
                    user_id = arg.updated_by
                elif hasattr(arg, 'activated_by') and user_id is None:
                    user_id = arg.activated_by
                elif hasattr(arg, 'paused_by') and user_id is None:
                    user_id = arg.paused_by
                elif hasattr(arg, 'allocated_by') and user_id is None:
                    user_id = arg.allocated_by
            
            if extract_resource_id:
                resource_id = extract_resource_id(*args, **kwargs)
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful audit event
                if tenant_id and user_id:
                    logger.log_audit_event(
                        event,
                        tenant_id,
                        user_id,
                        resource_id,
                        {"operation_result": "success"}
                    )
                
                return result
                
            except Exception as e:
                # Log failed audit event
                if tenant_id and user_id:
                    logger.log_audit_event(
                        AuditEvent.SYSTEM_ERROR,
                        tenant_id,
                        user_id,
                        resource_id,
                        {
                            "intended_operation": event.value,
                            "error": str(e),
                            "operation_result": "failure"
                        }
                    )
                
                raise
        
        return async_wrapper
    
    return decorator 