"""
Resource Manager for LangGraph Multi-Agent System

Provides comprehensive resource management capabilities including:
- Memory usage monitoring for long-running workflows
- Connection pooling optimization
- Workflow timeout handling improvements
- Agent execution throttling
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import threading
from concurrent.futures import ThreadPoolExecutor

from .error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources being managed."""
    MEMORY = "memory"
    CPU = "cpu"
    DATABASE_CONNECTIONS = "database_connections"
    NETWORK_CONNECTIONS = "network_connections"
    AGENT_INSTANCES = "agent_instances"
    WORKFLOW_INSTANCES = "workflow_instances"


class ThrottleStrategy(str, Enum):
    """Throttling strategies for resource management."""
    BLOCK = "block"  # Block until resources are available
    REJECT = "reject"  # Reject new requests when resources are exhausted
    QUEUE = "queue"  # Queue requests with timeout
    DEGRADE = "degrade"  # Reduce functionality but continue


@dataclass
class ResourceLimits:
    """Configuration for resource limits."""
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 90.0
    max_db_connections: int = 100
    max_network_connections: int = 200
    max_agent_instances: int = 50
    max_workflow_instances: int = 20
    memory_check_interval: int = 30  # seconds
    cleanup_interval: int = 300  # seconds


@dataclass
class ResourceUsage:
    """Current resource usage information."""
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    active_db_connections: int = 0
    active_network_connections: int = 0
    active_agent_instances: int = 0
    active_workflow_instances: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConnectionPool:
    """Connection pool configuration and state."""
    name: str
    max_size: int
    current_size: int = 0
    available_connections: int = 0
    in_use_connections: int = 0
    created_connections: int = 0
    failed_connections: int = 0
    last_cleanup: datetime = field(default_factory=datetime.now)


class ResourceManager:
    """Comprehensive resource manager with monitoring and throttling."""
    
    def __init__(
        self,
        limits: Optional[ResourceLimits] = None,
        error_handler: Optional[ErrorHandler] = None,
        enable_auto_cleanup: bool = True
    ):
        self.limits = limits or ResourceLimits()
        self.error_handler = error_handler or ErrorHandler()
        self.enable_auto_cleanup = enable_auto_cleanup
        
        # Resource tracking
        self._current_usage = ResourceUsage()
        self._usage_history: List[ResourceUsage] = []
        self._resource_locks: Dict[ResourceType, asyncio.Semaphore] = {}
        self._active_resources: Dict[ResourceType, Set[str]] = {
            resource_type: set() for resource_type in ResourceType
        }
        
        # Connection pools
        self._connection_pools: Dict[str, ConnectionPool] = {}
        self._pool_locks: Dict[str, asyncio.Lock] = {}
        
        # Throttling
        self._throttle_strategy = ThrottleStrategy.QUEUE
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._throttled_operations: Set[str] = set()
        
        # Monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
        # Timeout management
        self._active_timeouts: Dict[str, asyncio.Task] = {}
        self._timeout_handlers: Dict[str, Callable] = {}
        
        # Thread pool for CPU-intensive tasks
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        
        self._initialize_semaphores()
        
        logger.info("ResourceManager initialized with comprehensive monitoring")
    
    async def start_monitoring(self):
        """Start resource monitoring and cleanup tasks."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_resources())
        
        if self.enable_auto_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_resources())
        
        logger.info("Resource monitoring started")
    
    async def stop_monitoring(self):
        """Stop resource monitoring and cleanup tasks."""
        self._is_monitoring = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Resource monitoring stopped")
    
    @asynccontextmanager
    async def acquire_resource(
        self,
        resource_type: ResourceType,
        resource_id: str,
        timeout: Optional[float] = None
    ):
        """Acquire a resource with automatic release."""
        acquired = False
        try:
            # Check if we can acquire the resource
            if not await self._can_acquire_resource(resource_type):
                if self._throttle_strategy == ThrottleStrategy.REJECT:
                    raise Exception(f"Resource {resource_type.value} limit exceeded")
                elif self._throttle_strategy == ThrottleStrategy.BLOCK:
                    # Wait for resources to become available
                    await self._wait_for_resource(resource_type, timeout)
            
            # Acquire the resource
            semaphore = self._resource_locks[resource_type]
            if timeout:
                await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            else:
                await semaphore.acquire()
            
            acquired = True
            self._active_resources[resource_type].add(resource_id)
            
            logger.debug(f"Acquired resource {resource_type.value}: {resource_id}")
            yield resource_id
            
        except asyncio.TimeoutError:
            await self.error_handler.handle_error(
                Exception(f"Timeout acquiring resource {resource_type.value}"),
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.RESOURCE_LIMIT
            )
            raise
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.RESOURCE_LIMIT
            )
            raise
        finally:
            if acquired:
                # Release the resource
                self._active_resources[resource_type].discard(resource_id)
                self._resource_locks[resource_type].release()
                logger.debug(f"Released resource {resource_type.value}: {resource_id}")
    
    async def create_connection_pool(
        self,
        pool_name: str,
        max_size: int,
        connection_factory: Callable
    ) -> ConnectionPool:
        """Create a managed connection pool."""
        pool = ConnectionPool(name=pool_name, max_size=max_size)
        self._connection_pools[pool_name] = pool
        self._pool_locks[pool_name] = asyncio.Lock()
        
        logger.info(f"Created connection pool: {pool_name} (max_size: {max_size})")
        return pool
    
    @asynccontextmanager
    async def get_connection(self, pool_name: str, timeout: Optional[float] = None):
        """Get a connection from a managed pool."""
        pool = self._connection_pools.get(pool_name)
        if not pool:
            raise ValueError(f"Connection pool '{pool_name}' not found")
        
        connection = None
        try:
            async with self._pool_locks[pool_name]:
                if pool.available_connections > 0:
                    # Use existing connection (simulated)
                    pool.available_connections -= 1
                    pool.in_use_connections += 1
                elif pool.current_size < pool.max_size:
                    # Create new connection
                    pool.current_size += 1
                    pool.created_connections += 1
                    pool.in_use_connections += 1
                else:
                    # Pool is full, wait or reject
                    if timeout:
                        await asyncio.wait_for(
                            self._wait_for_pool_connection(pool_name), 
                            timeout=timeout
                        )
                    else:
                        raise Exception(f"Connection pool '{pool_name}' is full")
            
            # Simulate connection object
            connection = f"conn_{pool_name}_{int(time.time())}"
            logger.debug(f"Acquired connection from pool {pool_name}: {connection}")
            
            yield connection
            
        except Exception as e:
            pool.failed_connections += 1
            await self.error_handler.handle_error(
                e,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.RESOURCE_LIMIT
            )
            raise
        finally:
            if connection:
                # Return connection to pool
                async with self._pool_locks[pool_name]:
                    pool.in_use_connections -= 1
                    pool.available_connections += 1
                
                logger.debug(f"Returned connection to pool {pool_name}: {connection}")
    
    async def set_timeout(
        self,
        operation_id: str,
        timeout_seconds: float,
        timeout_handler: Optional[Callable] = None
    ):
        """Set a timeout for an operation with optional handler."""
        
        async def timeout_task():
            await asyncio.sleep(timeout_seconds)
            if operation_id in self._active_timeouts:
                logger.warning(f"Operation {operation_id} timed out after {timeout_seconds}s")
                
                if timeout_handler:
                    try:
                        if asyncio.iscoroutinefunction(timeout_handler):
                            await timeout_handler(operation_id)
                        else:
                            timeout_handler(operation_id)
                    except Exception as e:
                        await self.error_handler.handle_error(
                            e,
                            severity=ErrorSeverity.ERROR,
                            category=ErrorCategory.SYSTEM
                        )
                
                # Clean up
                del self._active_timeouts[operation_id]
                if operation_id in self._timeout_handlers:
                    del self._timeout_handlers[operation_id]
        
        # Cancel existing timeout if any
        if operation_id in self._active_timeouts:
            self._active_timeouts[operation_id].cancel()
        
        # Set new timeout
        self._active_timeouts[operation_id] = asyncio.create_task(timeout_task())
        if timeout_handler:
            self._timeout_handlers[operation_id] = timeout_handler
        
        logger.debug(f"Set timeout for operation {operation_id}: {timeout_seconds}s")
    
    async def clear_timeout(self, operation_id: str):
        """Clear a timeout for an operation."""
        if operation_id in self._active_timeouts:
            self._active_timeouts[operation_id].cancel()
            del self._active_timeouts[operation_id]
            
            if operation_id in self._timeout_handlers:
                del self._timeout_handlers[operation_id]
            
            logger.debug(f"Cleared timeout for operation: {operation_id}")
    
    async def throttle_operation(
        self,
        operation_id: str,
        resource_type: ResourceType,
        priority: int = 5  # 1-10, 1 is highest priority
    ):
        """Throttle an operation based on resource availability."""
        if not await self._should_throttle(resource_type):
            return  # No throttling needed
        
        self._throttled_operations.add(operation_id)
        
        try:
            # Add to queue with priority
            await self._request_queue.put((priority, operation_id, resource_type))
            
            # Wait for our turn
            while operation_id in self._throttled_operations:
                await asyncio.sleep(0.1)
            
        except Exception as e:
            self._throttled_operations.discard(operation_id)
            await self.error_handler.handle_error(
                e,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.RESOURCE_LIMIT
            )
            raise
    
    def get_resource_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        return self._current_usage
    
    def get_usage_history(self, hours: int = 24) -> List[ResourceUsage]:
        """Get resource usage history."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            usage for usage in self._usage_history
            if usage.timestamp >= cutoff_time
        ]
    
    def get_connection_pool_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all connection pools."""
        return {
            name: {
                "max_size": pool.max_size,
                "current_size": pool.current_size,
                "available_connections": pool.available_connections,
                "in_use_connections": pool.in_use_connections,
                "created_connections": pool.created_connections,
                "failed_connections": pool.failed_connections,
                "utilization_percent": (pool.in_use_connections / pool.max_size) * 100,
                "last_cleanup": pool.last_cleanup.isoformat()
            }
            for name, pool in self._connection_pools.items()
        }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        return {
            "current_usage": {
                "memory_percent": self._current_usage.memory_percent,
                "memory_mb": self._current_usage.memory_mb,
                "cpu_percent": self._current_usage.cpu_percent,
                "active_resources": {
                    resource_type.value: len(resources)
                    for resource_type, resources in self._active_resources.items()
                }
            },
            "limits": {
                "max_memory_percent": self.limits.max_memory_percent,
                "max_cpu_percent": self.limits.max_cpu_percent,
                "max_db_connections": self.limits.max_db_connections,
                "max_network_connections": self.limits.max_network_connections
            },
            "connection_pools": self.get_connection_pool_status(),
            "active_timeouts": len(self._active_timeouts),
            "throttled_operations": len(self._throttled_operations),
            "monitoring_active": self._is_monitoring
        }
    
    # Private helper methods
    
    def _initialize_semaphores(self):
        """Initialize semaphores for each resource type."""
        self._resource_locks = {
            ResourceType.MEMORY: asyncio.Semaphore(1),  # Single memory manager
            ResourceType.CPU: asyncio.Semaphore(4),  # 4 CPU-intensive operations
            ResourceType.DATABASE_CONNECTIONS: asyncio.Semaphore(self.limits.max_db_connections),
            ResourceType.NETWORK_CONNECTIONS: asyncio.Semaphore(self.limits.max_network_connections),
            ResourceType.AGENT_INSTANCES: asyncio.Semaphore(self.limits.max_agent_instances),
            ResourceType.WORKFLOW_INSTANCES: asyncio.Semaphore(self.limits.max_workflow_instances)
        }
    
    async def _monitor_resources(self):
        """Continuous resource monitoring task."""
        while self._is_monitoring:
            try:
                # Update current usage
                await self._update_resource_usage()
                
                # Check for resource violations
                await self._check_resource_violations()
                
                # Store usage history
                self._usage_history.append(self._current_usage)
                
                # Keep only last 24 hours of history
                cutoff_time = datetime.now() - timedelta(hours=24)
                self._usage_history = [
                    usage for usage in self._usage_history
                    if usage.timestamp >= cutoff_time
                ]
                
                await asyncio.sleep(self.limits.memory_check_interval)
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.SYSTEM
                )
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def _update_resource_usage(self):
        """Update current resource usage metrics."""
        try:
            # Get system metrics
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            process = psutil.Process()
            
            self._current_usage = ResourceUsage(
                memory_percent=memory_info.percent,
                memory_mb=process.memory_info().rss / 1024 / 1024,
                cpu_percent=cpu_percent,
                active_db_connections=len(self._active_resources[ResourceType.DATABASE_CONNECTIONS]),
                active_network_connections=len(self._active_resources[ResourceType.NETWORK_CONNECTIONS]),
                active_agent_instances=len(self._active_resources[ResourceType.AGENT_INSTANCES]),
                active_workflow_instances=len(self._active_resources[ResourceType.WORKFLOW_INSTANCES]),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to update resource usage: {e}")
    
    async def _check_resource_violations(self):
        """Check for resource limit violations."""
        usage = self._current_usage
        
        if usage.memory_percent > self.limits.max_memory_percent:
            await self.error_handler.handle_error(
                Exception(f"Memory usage exceeded limit: {usage.memory_percent}% > {self.limits.max_memory_percent}%"),
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.RESOURCE_LIMIT
            )
        
        if usage.cpu_percent > self.limits.max_cpu_percent:
            await self.error_handler.handle_error(
                Exception(f"CPU usage exceeded limit: {usage.cpu_percent}% > {self.limits.max_cpu_percent}%"),
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.RESOURCE_LIMIT
            )
    
    async def _cleanup_resources(self):
        """Periodic cleanup of resources."""
        while self._is_monitoring:
            try:
                await asyncio.sleep(self.limits.cleanup_interval)
                
                # Clean up expired timeouts
                expired_timeouts = [
                    op_id for op_id, task in self._active_timeouts.items()
                    if task.done()
                ]
                for op_id in expired_timeouts:
                    await self.clear_timeout(op_id)
                
                # Clean up connection pools
                for pool_name, pool in self._connection_pools.items():
                    if datetime.now() - pool.last_cleanup > timedelta(minutes=5):
                        await self._cleanup_connection_pool(pool_name)
                
                logger.debug("Resource cleanup completed")
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.SYSTEM
                )
    
    async def _cleanup_connection_pool(self, pool_name: str):
        """Clean up a specific connection pool."""
        pool = self._connection_pools[pool_name]
        
        async with self._pool_locks[pool_name]:
            # Simulate cleanup of idle connections
            idle_connections = pool.available_connections
            if idle_connections > pool.max_size // 2:  # Keep half as minimum
                connections_to_close = idle_connections - (pool.max_size // 2)
                pool.available_connections -= connections_to_close
                pool.current_size -= connections_to_close
                
                logger.debug(f"Cleaned up {connections_to_close} idle connections from pool {pool_name}")
            
            pool.last_cleanup = datetime.now()
    
    async def _can_acquire_resource(self, resource_type: ResourceType) -> bool:
        """Check if a resource can be acquired."""
        current_count = len(self._active_resources[resource_type])
        
        limits_map = {
            ResourceType.DATABASE_CONNECTIONS: self.limits.max_db_connections,
            ResourceType.NETWORK_CONNECTIONS: self.limits.max_network_connections,
            ResourceType.AGENT_INSTANCES: self.limits.max_agent_instances,
            ResourceType.WORKFLOW_INSTANCES: self.limits.max_workflow_instances
        }
        
        limit = limits_map.get(resource_type, float('inf'))
        return current_count < limit
    
    async def _wait_for_resource(self, resource_type: ResourceType, timeout: Optional[float]):
        """Wait for a resource to become available."""
        start_time = time.time()
        
        while not await self._can_acquire_resource(resource_type):
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Timeout waiting for {resource_type.value}")
            
            await asyncio.sleep(0.1)
    
    async def _wait_for_pool_connection(self, pool_name: str):
        """Wait for a connection to become available in a pool."""
        pool = self._connection_pools[pool_name]
        
        while pool.available_connections == 0 and pool.current_size >= pool.max_size:
            await asyncio.sleep(0.1)
    
    async def _should_throttle(self, resource_type: ResourceType) -> bool:
        """Determine if an operation should be throttled."""
        usage = self._current_usage
        
        # Throttle based on system resources
        if usage.memory_percent > self.limits.max_memory_percent * 0.9:
            return True
        
        if usage.cpu_percent > self.limits.max_cpu_percent * 0.9:
            return True
        
        # Throttle based on resource-specific limits
        current_count = len(self._active_resources[resource_type])
        limits_map = {
            ResourceType.DATABASE_CONNECTIONS: self.limits.max_db_connections,
            ResourceType.NETWORK_CONNECTIONS: self.limits.max_network_connections,
            ResourceType.AGENT_INSTANCES: self.limits.max_agent_instances,
            ResourceType.WORKFLOW_INSTANCES: self.limits.max_workflow_instances
        }
        
        limit = limits_map.get(resource_type, float('inf'))
        return current_count > limit * 0.8  # Throttle at 80% capacity 