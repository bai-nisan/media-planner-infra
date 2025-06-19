"""
Enhanced State Manager for LangGraph Multi-Agent System

Provides advanced state management capabilities including:
- Rate limiting for agent operations
- Resource management and concurrent execution limits
- State recovery mechanisms for workflow interruptions
- Cross-tenant state isolation improvements
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import psutil

from .error_handler import ErrorHandler, ErrorSeverity
from .workflows.state_models import AgentRole, AgentState, WorkflowStage

logger = logging.getLogger(__name__)


class StateOperationType(str, Enum):
    """Types of state operations for rate limiting."""

    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    RECOVERY = "recovery"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests_per_minute: int = 60
    max_requests_per_second: int = 10
    burst_allowance: int = 5
    tenant_isolation: bool = True
    operation_weights: Dict[StateOperationType, float] = field(
        default_factory=lambda: {
            StateOperationType.READ: 1.0,
            StateOperationType.WRITE: 2.0,
            StateOperationType.UPDATE: 1.5,
            StateOperationType.DELETE: 3.0,
            StateOperationType.RECOVERY: 5.0,
        }
    )


@dataclass
class ResourceLimits:
    """Resource limits for state operations."""

    max_concurrent_operations: int = 50
    max_memory_usage_mb: int = 512
    max_state_size_mb: int = 100
    operation_timeout_seconds: int = 30
    recovery_timeout_seconds: int = 300


@dataclass
class TenantStateInfo:
    """Information about a tenant's state usage."""

    tenant_id: str
    active_operations: int = 0
    total_operations: int = 0
    memory_usage_mb: float = 0.0
    last_operation_time: datetime = field(default_factory=datetime.now)
    rate_limit_violations: int = 0
    error_count: int = 0


class StateManager:
    """Advanced state manager with rate limiting and resource management."""

    def __init__(
        self,
        supabase_client=None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        resource_limits: Optional[ResourceLimits] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        self.supabase_client = supabase_client
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.resource_limits = resource_limits or ResourceLimits()
        self.error_handler = error_handler

        # Rate limiting tracking
        self._request_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._tenant_state_info: Dict[str, TenantStateInfo] = {}
        self._global_operation_count = 0

        # Resource management
        self._active_operations: Set[str] = set()
        self._operation_semaphore = asyncio.Semaphore(
            self.resource_limits.max_concurrent_operations
        )
        self._state_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Recovery mechanisms
        self._recovery_checkpoints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._interrupted_workflows: Dict[str, AgentState] = {}

        # Monitoring
        self._metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "rate_limit_violations": 0,
            "resource_limit_violations": 0,
            "recovery_operations": 0,
        }

        logger.info("StateManager initialized with enhanced capabilities")

    async def save_state(
        self,
        state_id: str,
        state_data: AgentState,
        tenant_id: Optional[str] = None,
        agent_role: Optional[AgentRole] = None,
        create_checkpoint: bool = True,
    ) -> bool:
        """Save agent state with rate limiting and resource management."""
        operation_id = f"save_{state_id}_{int(time.time())}"

        try:
            # Check rate limits
            if not await self._check_rate_limits(
                tenant_id or "global", StateOperationType.WRITE
            ):
                await self._handle_rate_limit_violation(tenant_id, operation_id)
                return False

            # Check resource limits
            if not await self._check_resource_limits(state_data, operation_id):
                return False

            async with self._operation_semaphore:
                self._active_operations.add(operation_id)

                try:
                    # Create checkpoint if requested
                    if create_checkpoint:
                        await self._create_checkpoint(state_id, state_data, tenant_id)

                    # Prepare state data for persistence
                    serialized_state = await self._serialize_state(state_data)

                    # Save to Supabase with tenant isolation
                    if self.supabase_client:
                        state_record = {
                            "state_id": state_id,
                            "tenant_id": tenant_id,
                            "agent_role": agent_role.value if agent_role else None,
                            "state_data": serialized_state,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                            "checksum": await self._calculate_checksum(
                                serialized_state
                            ),
                        }

                        await self.supabase_client.table("agent_states").upsert(
                            state_record
                        ).execute()

                    # Update cache
                    cache_key = f"{tenant_id}:{state_id}" if tenant_id else state_id
                    self._state_cache[cache_key] = serialized_state
                    self._cache_timestamps[cache_key] = datetime.now()

                    # Update metrics and tenant info
                    await self._update_operation_metrics(tenant_id, True)

                    logger.debug(f"State saved successfully: {state_id}")
                    return True

                finally:
                    self._active_operations.discard(operation_id)

        except Exception as e:
            await self._handle_operation_error(e, operation_id, tenant_id)
            return False

    async def load_state(
        self, state_id: str, tenant_id: Optional[str] = None, use_cache: bool = True
    ) -> Optional[AgentState]:
        """Load agent state with caching and tenant isolation."""
        operation_id = f"load_{state_id}_{int(time.time())}"

        try:
            # Check rate limits
            if not await self._check_rate_limits(
                tenant_id or "global", StateOperationType.READ
            ):
                await self._handle_rate_limit_violation(tenant_id, operation_id)
                return None

            # Try cache first
            cache_key = f"{tenant_id}:{state_id}" if tenant_id else state_id
            if use_cache and cache_key in self._state_cache:
                cache_time = self._cache_timestamps.get(cache_key)
                if (
                    cache_time and (datetime.now() - cache_time).seconds < 300
                ):  # 5 min cache
                    logger.debug(f"State loaded from cache: {state_id}")
                    return await self._deserialize_state(self._state_cache[cache_key])

            async with self._operation_semaphore:
                self._active_operations.add(operation_id)

                try:
                    if self.supabase_client:
                        query = (
                            self.supabase_client.table("agent_states")
                            .select("state_data")
                            .eq("state_id", state_id)
                        )

                        # Add tenant isolation
                        if tenant_id:
                            query = query.eq("tenant_id", tenant_id)

                        result = (
                            await query.order("created_at", desc=True)
                            .limit(1)
                            .execute()
                        )

                        if result.data:
                            state_data = result.data[0]["state_data"]

                            # Update cache
                            self._state_cache[cache_key] = state_data
                            self._cache_timestamps[cache_key] = datetime.now()

                            await self._update_operation_metrics(tenant_id, True)
                            return await self._deserialize_state(state_data)

                    return None

                finally:
                    self._active_operations.discard(operation_id)

        except Exception as e:
            await self._handle_operation_error(e, operation_id, tenant_id)
            return None

    async def recover_workflow_state(
        self,
        workflow_id: str,
        tenant_id: Optional[str] = None,
        checkpoint_index: int = -1,
    ) -> Optional[AgentState]:
        """Recover workflow state from checkpoints."""
        operation_id = f"recover_{workflow_id}_{int(time.time())}"

        try:
            # Check rate limits for recovery operation
            if not await self._check_rate_limits(
                tenant_id or "global", StateOperationType.RECOVERY
            ):
                return None

            checkpoints = self._recovery_checkpoints.get(workflow_id, [])
            if not checkpoints:
                logger.warning(f"No checkpoints found for workflow: {workflow_id}")
                return None

            # Get checkpoint (default to latest)
            if checkpoint_index < 0:
                checkpoint_index = len(checkpoints) + checkpoint_index

            if 0 <= checkpoint_index < len(checkpoints):
                checkpoint_data = checkpoints[checkpoint_index]
                recovered_state = await self._deserialize_state(checkpoint_data)

                self._metrics["recovery_operations"] += 1
                logger.info(f"Workflow state recovered: {workflow_id}")

                return recovered_state

            return None

        except Exception as e:
            await self._handle_operation_error(e, operation_id, tenant_id)
            return None

    async def cleanup_tenant_state(
        self, tenant_id: str, older_than_hours: int = 24
    ) -> int:
        """Clean up old state data for a tenant."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

            if self.supabase_client:
                result = (
                    await self.supabase_client.table("agent_states")
                    .delete()
                    .eq("tenant_id", tenant_id)
                    .lt("created_at", cutoff_time.isoformat())
                    .execute()
                )

                deleted_count = len(result.data) if result.data else 0

                # Clean up cache
                cache_keys_to_remove = [
                    key
                    for key in self._state_cache.keys()
                    if key.startswith(f"{tenant_id}:")
                ]
                for key in cache_keys_to_remove:
                    del self._state_cache[key]
                    del self._cache_timestamps[key]

                logger.info(
                    f"Cleaned up {deleted_count} old states for tenant: {tenant_id}"
                )
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Failed to cleanup tenant state: {e}")
            return 0

    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics for a specific tenant."""
        tenant_info = self._tenant_state_info.get(tenant_id, TenantStateInfo(tenant_id))

        return {
            "tenant_id": tenant_id,
            "active_operations": tenant_info.active_operations,
            "total_operations": tenant_info.total_operations,
            "memory_usage_mb": tenant_info.memory_usage_mb,
            "last_operation_time": tenant_info.last_operation_time.isoformat(),
            "rate_limit_violations": tenant_info.rate_limit_violations,
            "error_count": tenant_info.error_count,
            "cache_entries": len(
                [k for k in self._state_cache.keys() if k.startswith(f"{tenant_id}:")]
            ),
            "checkpoints": len(self._recovery_checkpoints.get(tenant_id, [])),
        }

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics."""
        memory_info = psutil.virtual_memory()
        process = psutil.Process()

        return {
            "global_metrics": self._metrics.copy(),
            "active_operations": len(self._active_operations),
            "cached_states": len(self._state_cache),
            "total_tenants": len(self._tenant_state_info),
            "system_memory_percent": memory_info.percent,
            "process_memory_mb": process.memory_info().rss / 1024 / 1024,
            "recovery_checkpoints": sum(
                len(cp) for cp in self._recovery_checkpoints.values()
            ),
            "rate_limit_config": {
                "max_requests_per_minute": self.rate_limit_config.max_requests_per_minute,
                "max_requests_per_second": self.rate_limit_config.max_requests_per_second,
                "burst_allowance": self.rate_limit_config.burst_allowance,
            },
            "resource_limits": {
                "max_concurrent_operations": self.resource_limits.max_concurrent_operations,
                "max_memory_usage_mb": self.resource_limits.max_memory_usage_mb,
                "max_state_size_mb": self.resource_limits.max_state_size_mb,
            },
        }

    # Private helper methods

    async def _check_rate_limits(
        self, tenant_id: str, operation_type: StateOperationType
    ) -> bool:
        """Check if operation is within rate limits."""
        now = time.time()
        weight = self.rate_limit_config.operation_weights.get(operation_type, 1.0)

        # Clean old requests
        request_history = self._request_history[tenant_id]
        while (
            request_history and now - request_history[0] > 60
        ):  # Remove requests older than 1 minute
            request_history.popleft()

        # Count recent requests
        recent_requests = sum(1 for req_time in request_history if now - req_time <= 60)
        very_recent_requests = sum(
            1 for req_time in request_history if now - req_time <= 1
        )

        # Apply weights
        weighted_recent = recent_requests * weight
        weighted_very_recent = very_recent_requests * weight

        # Check limits
        per_minute_ok = weighted_recent < self.rate_limit_config.max_requests_per_minute
        per_second_ok = (
            weighted_very_recent < self.rate_limit_config.max_requests_per_second
        )

        if per_minute_ok and per_second_ok:
            request_history.append(now)
            return True

        return False

    async def _check_resource_limits(
        self, state_data: AgentState, operation_id: str
    ) -> bool:
        """Check if operation is within resource limits."""
        # Check concurrent operations
        if (
            len(self._active_operations)
            >= self.resource_limits.max_concurrent_operations
        ):
            self._metrics["resource_limit_violations"] += 1
            logger.warning(f"Concurrent operation limit exceeded: {operation_id}")
            return False

        # Check memory usage
        process = psutil.Process()
        current_memory_mb = process.memory_info().rss / 1024 / 1024

        if current_memory_mb > self.resource_limits.max_memory_usage_mb:
            self._metrics["resource_limit_violations"] += 1
            logger.warning(
                f"Memory limit exceeded: {current_memory_mb}MB > {self.resource_limits.max_memory_usage_mb}MB"
            )
            return False

        # Check state size
        try:
            state_json = json.dumps(state_data.dict(), default=str)
            state_size_mb = len(state_json.encode("utf-8")) / 1024 / 1024

            if state_size_mb > self.resource_limits.max_state_size_mb:
                self._metrics["resource_limit_violations"] += 1
                logger.warning(
                    f"State size limit exceeded: {state_size_mb}MB > {self.resource_limits.max_state_size_mb}MB"
                )
                return False
        except Exception as e:
            logger.error(f"Failed to check state size: {e}")
            return False

        return True

    async def _create_checkpoint(
        self, state_id: str, state_data: AgentState, tenant_id: Optional[str]
    ):
        """Create a recovery checkpoint."""
        try:
            checkpoint_key = tenant_id or "global"
            checkpoint_data = await self._serialize_state(state_data)

            # Add timestamp to checkpoint
            checkpoint_data["checkpoint_timestamp"] = datetime.now().isoformat()
            checkpoint_data["state_id"] = state_id

            checkpoints = self._recovery_checkpoints[checkpoint_key]
            checkpoints.append(checkpoint_data)

            # Keep only last 10 checkpoints
            if len(checkpoints) > 10:
                checkpoints.pop(0)

            logger.debug(f"Checkpoint created for state: {state_id}")

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")

    async def _serialize_state(self, state_data: AgentState) -> Dict[str, Any]:
        """Serialize state data for storage."""
        return state_data.dict()

    async def _deserialize_state(self, state_data: Dict[str, Any]) -> AgentState:
        """Deserialize state data from storage."""
        return AgentState(**state_data)

    async def _calculate_checksum(self, state_data: Dict[str, Any]) -> str:
        """Calculate checksum for state data integrity."""
        import hashlib

        data_str = json.dumps(state_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    async def _handle_rate_limit_violation(
        self, tenant_id: Optional[str], operation_id: str
    ):
        """Handle rate limit violation."""
        self._metrics["rate_limit_violations"] += 1

        if tenant_id:
            tenant_info = self._tenant_state_info.setdefault(
                tenant_id, TenantStateInfo(tenant_id)
            )
            tenant_info.rate_limit_violations += 1

        logger.warning(f"Rate limit violation for operation: {operation_id}")

        if self.error_handler:
            await self.error_handler.handle_error(
                Exception(f"Rate limit exceeded for operation: {operation_id}"),
                severity=ErrorSeverity.WARNING,
                context={"tenant_id": tenant_id, "operation_id": operation_id},
            )

    async def _handle_operation_error(
        self, error: Exception, operation_id: str, tenant_id: Optional[str]
    ):
        """Handle operation errors."""
        self._metrics["failed_operations"] += 1

        if tenant_id:
            tenant_info = self._tenant_state_info.setdefault(
                tenant_id, TenantStateInfo(tenant_id)
            )
            tenant_info.error_count += 1

        logger.error(f"Operation error: {operation_id} - {error}")

        if self.error_handler:
            await self.error_handler.handle_error(
                error,
                severity=ErrorSeverity.ERROR,
                context={"operation_id": operation_id, "tenant_id": tenant_id},
            )

    async def _update_operation_metrics(self, tenant_id: Optional[str], success: bool):
        """Update operation metrics."""
        self._metrics["total_operations"] += 1

        if success:
            self._metrics["successful_operations"] += 1
        else:
            self._metrics["failed_operations"] += 1

        if tenant_id:
            tenant_info = self._tenant_state_info.setdefault(
                tenant_id, TenantStateInfo(tenant_id)
            )
            tenant_info.total_operations += 1
            tenant_info.last_operation_time = datetime.now()
