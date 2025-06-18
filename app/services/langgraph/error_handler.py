"""
Advanced Error Handler for LangGraph Multi-Agent System

Provides comprehensive error handling capabilities including:
- Circuit breaker pattern for external API calls
- Retry mechanisms with exponential backoff
- Centralized error reporting and alerting
- Error categorization (recoverable vs non-recoverable)
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import traceback
import json
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    NETWORK = "network"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    RESOURCE_LIMIT = "resource_limit"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_API = "external_api"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    error_id: str
    timestamp: datetime
    error_type: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: Dict[str, Any]
    traceback: Optional[str] = None
    resolution_attempted: bool = False
    resolved: bool = False
    retry_count: int = 0


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_factor: float = 2.0
    jitter: bool = True
    retry_on: List[Exception] = field(default_factory=lambda: [Exception])
    dont_retry_on: List[Exception] = field(default_factory=list)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: Exception = Exception
    name: Optional[str] = None


class CircuitBreaker:
    """Circuit breaker implementation for external API calls."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self.name = config.name or "unnamed"
        
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.config.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.info(f"Circuit breaker {self.name} reset to CLOSED")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")


class ErrorHandler:
    """Centralized error handler with advanced capabilities."""
    
    def __init__(self, enable_alerting: bool = True):
        self.enable_alerting = enable_alerting
        self.error_records: List[ErrorRecord] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_counts: Dict[str, int] = {}
        self.resolution_strategies: Dict[ErrorCategory, Callable] = {}
        
        # Initialize default resolution strategies
        self._setup_default_strategies()
        
        logger.info("ErrorHandler initialized with advanced capabilities")
    
    async def handle_error(
        self,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: Optional[ErrorCategory] = None,
        context: Optional[Dict[str, Any]] = None,
        attempt_resolution: bool = True
    ) -> ErrorRecord:
        """Handle an error with comprehensive processing."""
        
        # Generate error ID
        error_id = f"err_{int(time.time() * 1000)}"
        
        # Categorize error if not provided
        if category is None:
            category = self._categorize_error(error)
        
        # Create error record
        error_record = ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            error_type=type(error).__name__,
            message=str(error),
            severity=severity,
            category=category,
            context=context or {},
            traceback=traceback.format_exc()
        )
        
        # Store error record
        self.error_records.append(error_record)
        self.error_counts[category.value] = self.error_counts.get(category.value, 0) + 1
        
        # Log error
        log_level = self._get_log_level(severity)
        logger.log(
            log_level,
            f"Error {error_id}: {error_record.message}",
            extra={
                "error_id": error_id,
                "category": category.value,
                "severity": severity.value,
                "context": context
            }
        )
        
        # Attempt resolution if enabled
        if attempt_resolution:
            await self._attempt_error_resolution(error_record)
        
        # Send alerts for critical errors
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL] and self.enable_alerting:
            await self._send_alert(error_record)
        
        return error_record
    
    def create_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Create and register a circuit breaker."""
        if config is None:
            config = CircuitBreakerConfig(name=name)
        
        circuit_breaker = CircuitBreaker(config)
        self.circuit_breakers[name] = circuit_breaker
        
        logger.info(f"Circuit breaker created: {name}")
        return circuit_breaker
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    async def retry_with_backoff(
        self,
        func: Callable,
        config: Optional[RetryConfig] = None,
        *args,
        **kwargs
    ):
        """Execute function with retry and exponential backoff."""
        if config is None:
            config = RetryConfig()
        
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                # Check if we should retry this exception
                if not self._should_retry_exception(e, config):
                    break
                
                # Don't sleep on the last attempt
                if attempt < config.max_attempts - 1:
                    delay = self._calculate_delay(attempt, config)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
        
        # All attempts failed
        if last_exception:
            await self.handle_error(
                last_exception,
                severity=ErrorSeverity.ERROR,
                context={"retry_attempts": config.max_attempts, "function": func.__name__}
            )
            raise last_exception
    
    def register_resolution_strategy(
        self,
        category: ErrorCategory,
        strategy: Callable[[ErrorRecord], bool]
    ):
        """Register a resolution strategy for an error category."""
        self.resolution_strategies[category] = strategy
        logger.info(f"Resolution strategy registered for category: {category.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        total_errors = len(self.error_records)
        
        if total_errors == 0:
            return {"total_errors": 0, "error_rates": {}, "recent_errors": []}
        
        # Calculate error rates by category
        error_rates = {}
        for category, count in self.error_counts.items():
            error_rates[category] = (count / total_errors) * 100
        
        # Get recent errors (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_errors = [
            {
                "error_id": err.error_id,
                "timestamp": err.timestamp.isoformat(),
                "category": err.category.value,
                "severity": err.severity.value,
                "message": err.message[:100] + "..." if len(err.message) > 100 else err.message
            }
            for err in self.error_records
            if err.timestamp >= cutoff_time
        ]
        
        # Circuit breaker status
        circuit_status = {
            name: {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "last_failure": cb.last_failure_time
            }
            for name, cb in self.circuit_breakers.items()
        }
        
        return {
            "total_errors": total_errors,
            "error_rates": error_rates,
            "recent_errors": recent_errors[-10:],  # Last 10 recent errors
            "circuit_breakers": circuit_status,
            "resolution_attempts": sum(1 for err in self.error_records if err.resolution_attempted),
            "resolved_errors": sum(1 for err in self.error_records if err.resolved)
        }
    
    # Private helper methods
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Automatically categorize an error."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        if "network" in error_message or "connection" in error_message:
            return ErrorCategory.NETWORK
        elif "database" in error_message or "sql" in error_message:
            return ErrorCategory.DATABASE
        elif "auth" in error_message or "permission" in error_message:
            return ErrorCategory.AUTHENTICATION
        elif "validation" in error_message or "invalid" in error_message:
            return ErrorCategory.VALIDATION
        elif "rate limit" in error_message or "too many" in error_message:
            return ErrorCategory.RATE_LIMIT
        elif "memory" in error_message or "resource" in error_message:
            return ErrorCategory.RESOURCE_LIMIT
        elif "api" in error_message or "http" in error_message:
            return ErrorCategory.EXTERNAL_API
        else:
            return ErrorCategory.UNKNOWN
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Get logging level for error severity."""
        severity_map = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.FATAL: logging.CRITICAL
        }
        return severity_map.get(severity, logging.ERROR)
    
    async def _attempt_error_resolution(self, error_record: ErrorRecord):
        """Attempt to resolve an error using registered strategies."""
        error_record.resolution_attempted = True
        
        strategy = self.resolution_strategies.get(error_record.category)
        if strategy:
            try:
                resolved = await strategy(error_record) if asyncio.iscoroutinefunction(strategy) else strategy(error_record)
                error_record.resolved = resolved
                
                if resolved:
                    logger.info(f"Error {error_record.error_id} resolved using strategy for {error_record.category.value}")
                
            except Exception as e:
                logger.error(f"Error resolution strategy failed: {e}")
    
    async def _send_alert(self, error_record: ErrorRecord):
        """Send alert for critical errors."""
        # In a real implementation, this would integrate with alerting systems
        # like Slack, PagerDuty, email, etc.
        alert_message = f"CRITICAL ERROR: {error_record.error_id}\n"
        alert_message += f"Category: {error_record.category.value}\n"
        alert_message += f"Message: {error_record.message}\n"
        alert_message += f"Timestamp: {error_record.timestamp}\n"
        
        logger.critical(f"ALERT SENT: {alert_message}")
    
    def _should_retry_exception(self, exception: Exception, config: RetryConfig) -> bool:
        """Determine if an exception should be retried."""
        # Check dont_retry_on list first
        for exc_type in config.dont_retry_on:
            if isinstance(exception, exc_type):
                return False
        
        # Check retry_on list
        for exc_type in config.retry_on:
            if isinstance(exception, exc_type):
                return True
        
        return False
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for exponential backoff."""
        delay = config.base_delay * (config.exponential_factor ** attempt)
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def _setup_default_strategies(self):
        """Setup default error resolution strategies."""
        
        async def network_error_strategy(error_record: ErrorRecord) -> bool:
            """Default strategy for network errors."""
            # Simple strategy: wait and hope the network issue resolves
            await asyncio.sleep(5)
            return False  # Can't automatically resolve network issues
        
        async def rate_limit_strategy(error_record: ErrorRecord) -> bool:
            """Default strategy for rate limit errors."""
            # Wait for rate limit to reset
            await asyncio.sleep(60)
            return True  # Rate limits typically auto-resolve
        
        self.register_resolution_strategy(ErrorCategory.NETWORK, network_error_strategy)
        self.register_resolution_strategy(ErrorCategory.RATE_LIMIT, rate_limit_strategy)


# Decorator for automatic error handling
def handle_errors(
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: Optional[ErrorCategory] = None,
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_name: Optional[str] = None
):
    """Decorator for automatic error handling and retry."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            
            # Use circuit breaker if specified
            if circuit_breaker_name:
                cb = error_handler.get_circuit_breaker(circuit_breaker_name)
                if cb:
                    return await cb.call(func, *args, **kwargs)
            
            # Use retry mechanism if specified
            if retry_config:
                return await error_handler.retry_with_backoff(func, retry_config, *args, **kwargs)
            
            # Simple error handling
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_error(e, severity, category)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Note: sync version can't use async error handling
                logger.error(f"Error in {func.__name__}: {e}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator 