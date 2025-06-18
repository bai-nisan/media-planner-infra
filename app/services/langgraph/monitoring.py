"""
Monitoring and Observability Service for LangGraph Multi-Agent System

Provides comprehensive monitoring capabilities including:
- Performance metrics collection
- Agent execution tracing
- State transition monitoring
- Resource utilization tracking
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import threading
from contextlib import contextmanager
import uuid

from .state_models import AgentRole, WorkflowStage, AgentState
from .error_handler import ErrorHandler, ErrorSeverity

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics being collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    TRACE = "trace"


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: Union[float, int]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEvent:
    """Agent execution trace event."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    agent_role: Optional[AgentRole]
    workflow_stage: Optional[WorkflowStage]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "started"  # started, completed, failed
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    operation: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    average_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    last_call_time: Optional[datetime] = None
    error_rate: float = 0.0


@dataclass
class AlertRule:
    """Configuration for monitoring alerts."""
    name: str
    condition: str  # e.g., "error_rate > 0.1" or "avg_duration > 5000"
    level: AlertLevel
    threshold_value: float
    time_window_minutes: int = 5
    enabled: bool = True
    cooldown_minutes: int = 15  # Minimum time between alerts
    last_triggered: Optional[datetime] = None


class MonitoringService:
    """Comprehensive monitoring and observability service."""
    
    def __init__(
        self,
        error_handler: Optional[ErrorHandler] = None,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        enable_alerting: bool = True,
        metrics_retention_hours: int = 24
    ):
        self.error_handler = error_handler or ErrorHandler()
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.enable_alerting = enable_alerting
        self.metrics_retention_hours = metrics_retention_hours
        
        # Metrics storage
        self._metrics: List[MetricPoint] = []
        self._metrics_lock = threading.Lock()
        self._performance_metrics: Dict[str, PerformanceMetrics] = {}
        
        # Tracing storage
        self._traces: Dict[str, List[TraceEvent]] = defaultdict(list)
        self._active_spans: Dict[str, TraceEvent] = {}
        self._traces_lock = threading.Lock()
        
        # State monitoring
        self._state_transitions: List[Dict[str, Any]] = []
        self._agent_status: Dict[AgentRole, Dict[str, Any]] = {}
        
        # Alerting
        self._alert_rules: List[AlertRule] = []
        self._triggered_alerts: List[Dict[str, Any]] = []
        self._alert_callbacks: List[Callable] = []
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
        # Setup default alert rules
        self._setup_default_alert_rules()
        
        logger.info("MonitoringService initialized with comprehensive observability")
    
    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Monitoring service started")
    
    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
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
        
        logger.info("Monitoring service stopped")
    
    # Metrics Collection
    
    def record_metric(
        self,
        name: str,
        value: Union[float, int],
        metric_type: MetricType = MetricType.GAUGE,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a metric data point."""
        if not self.enable_metrics:
            return
        
        metric_point = MetricPoint(
            name=name,
            value=value,
            metric_type=metric_type,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        with self._metrics_lock:
            self._metrics.append(metric_point)
        
        logger.debug(f"Recorded metric: {name} = {value}")
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        self.record_metric(name, value, MetricType.COUNTER, tags)
    
    def set_gauge(self, name: str, value: Union[float, int], tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric value."""
        self.record_metric(name, value, MetricType.GAUGE, tags)
    
    @contextmanager
    def time_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        start_time = time.time()
        error_occurred = False
        
        try:
            yield
        except Exception as e:
            error_occurred = True
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record timing metric
            self.record_metric(
                f"{operation_name}.duration",
                duration_ms,
                MetricType.TIMER,
                tags
            )
            
            # Update performance metrics
            self._update_performance_metrics(operation_name, duration_ms, not error_occurred)
    
    # Distributed Tracing
    
    def start_trace(
        self,
        operation: str,
        agent_role: Optional[AgentRole] = None,
        workflow_stage: Optional[WorkflowStage] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new trace span."""
        if not self.enable_tracing:
            return ""
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        trace_event = TraceEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation=operation,
            agent_role=agent_role,
            workflow_stage=workflow_stage,
            start_time=datetime.now(),
            metadata=metadata or {}
        )
        
        with self._traces_lock:
            self._traces[trace_id].append(trace_event)
            self._active_spans[span_id] = trace_event
        
        logger.debug(f"Started trace: {operation} (span: {span_id})")
        return span_id
    
    def end_trace(
        self,
        span_id: str,
        status: str = "completed",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """End a trace span."""
        if not self.enable_tracing or not span_id:
            return
        
        with self._traces_lock:
            if span_id in self._active_spans:
                trace_event = self._active_spans[span_id]
                trace_event.end_time = datetime.now()
                trace_event.duration_ms = (
                    trace_event.end_time - trace_event.start_time
                ).total_seconds() * 1000
                trace_event.status = status
                trace_event.error = error
                
                if metadata:
                    trace_event.metadata.update(metadata)
                
                del self._active_spans[span_id]
                
                logger.debug(f"Ended trace: {trace_event.operation} ({trace_event.duration_ms:.2f}ms)")
    
    @contextmanager
    def trace_operation(
        self,
        operation: str,
        agent_role: Optional[AgentRole] = None,
        workflow_stage: Optional[WorkflowStage] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager for tracing operations."""
        span_id = self.start_trace(operation, agent_role, workflow_stage, metadata=metadata)
        error_occurred = False
        error_message = None
        
        try:
            yield span_id
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            raise
        finally:
            status = "failed" if error_occurred else "completed"
            self.end_trace(span_id, status, error_message)
    
    # State Monitoring
    
    def record_state_transition(
        self,
        from_stage: WorkflowStage,
        to_stage: WorkflowStage,
        agent_role: Optional[AgentRole] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a workflow state transition."""
        transition = {
            "timestamp": datetime.now().isoformat(),
            "from_stage": from_stage.value,
            "to_stage": to_stage.value,
            "agent_role": agent_role.value if agent_role else None,
            "metadata": metadata or {}
        }
        
        self._state_transitions.append(transition)
        
        # Record metric
        self.increment_counter(
            "state_transitions",
            tags={
                "from_stage": from_stage.value,
                "to_stage": to_stage.value,
                "agent_role": agent_role.value if agent_role else "unknown"
            }
        )
        
        logger.debug(f"State transition: {from_stage.value} -> {to_stage.value}")
    
    def update_agent_status(
        self,
        agent_role: AgentRole,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update agent status."""
        self._agent_status[agent_role] = {
            "status": status,
            "last_updated": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Record metric
        self.set_gauge(
            "agent_status",
            1 if status == "healthy" else 0,
            tags={"agent_role": agent_role.value, "status": status}
        )
    
    # Alerting
    
    def add_alert_rule(self, alert_rule: AlertRule):
        """Add a new alert rule."""
        self._alert_rules.append(alert_rule)
        logger.info(f"Added alert rule: {alert_rule.name}")
    
    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add a callback for alert notifications."""
        self._alert_callbacks.append(callback)
    
    # Data Retrieval
    
    def get_metrics(
        self,
        name_pattern: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[MetricPoint]:
        """Get metrics matching the specified criteria."""
        with self._metrics_lock:
            filtered_metrics = self._metrics.copy()
        
        # Apply filters
        if name_pattern:
            filtered_metrics = [m for m in filtered_metrics if name_pattern in m.name]
        
        if start_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= start_time]
        
        if end_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp <= end_time]
        
        if tags:
            filtered_metrics = [
                m for m in filtered_metrics
                if all(m.tags.get(k) == v for k, v in tags.items())
            ]
        
        return filtered_metrics
    
    def get_traces(
        self,
        trace_id: Optional[str] = None,
        operation: Optional[str] = None,
        agent_role: Optional[AgentRole] = None
    ) -> Dict[str, List[TraceEvent]]:
        """Get traces matching the specified criteria."""
        with self._traces_lock:
            if trace_id:
                return {trace_id: self._traces.get(trace_id, [])}
            
            filtered_traces = {}
            for tid, events in self._traces.items():
                if operation and not any(e.operation == operation for e in events):
                    continue
                if agent_role and not any(e.agent_role == agent_role for e in events):
                    continue
                filtered_traces[tid] = events
            
            return filtered_traces
    
    def get_performance_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get aggregated performance metrics."""
        return self._performance_metrics.copy()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        recent_errors = self._get_recent_error_count()
        avg_response_time = self._get_average_response_time()
        active_operations = len(self._active_spans)
        
        # Determine health status
        if recent_errors > 10 or avg_response_time > 5000:
            health_status = "unhealthy"
        elif recent_errors > 5 or avg_response_time > 2000:
            health_status = "degraded"
        else:
            health_status = "healthy"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "recent_errors": recent_errors,
                "average_response_time_ms": avg_response_time,
                "active_operations": active_operations,
                "total_traces": len(self._traces),
                "total_metrics": len(self._metrics),
                "agent_status": {
                    role.value: status["status"]
                    for role, status in self._agent_status.items()
                }
            },
            "alerts": {
                "active_rules": len([r for r in self._alert_rules if r.enabled]),
                "recent_triggers": len([
                    a for a in self._triggered_alerts
                    if datetime.fromisoformat(a["timestamp"]) > datetime.now() - timedelta(hours=1)
                ])
            }
        }
    
    # Private methods
    
    def _update_performance_metrics(self, operation: str, duration_ms: float, success: bool):
        """Update aggregated performance metrics."""
        if operation not in self._performance_metrics:
            self._performance_metrics[operation] = PerformanceMetrics(operation=operation)
        
        metrics = self._performance_metrics[operation]
        metrics.total_calls += 1
        metrics.last_call_time = datetime.now()
        
        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
        
        # Update duration statistics
        metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
        metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)
        
        # Calculate running average
        if metrics.total_calls == 1:
            metrics.average_duration_ms = duration_ms
        else:
            metrics.average_duration_ms = (
                (metrics.average_duration_ms * (metrics.total_calls - 1) + duration_ms) /
                metrics.total_calls
            )
        
        # Update error rate
        metrics.error_rate = metrics.failed_calls / metrics.total_calls
    
    async def _monitoring_loop(self):
        """Main monitoring loop for checking alerts."""
        while self._is_monitoring:
            try:
                if self.enable_alerting:
                    await self._check_alert_rules()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.ERROR,
                    context={"component": "monitoring_loop"}
                )
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self):
        """Cleanup old metrics and traces."""
        while self._is_monitoring:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour
                
                cutoff_time = datetime.now() - timedelta(hours=self.metrics_retention_hours)
                
                # Clean up metrics
                with self._metrics_lock:
                    self._metrics = [m for m in self._metrics if m.timestamp >= cutoff_time]
                
                # Clean up traces
                with self._traces_lock:
                    traces_to_remove = []
                    for trace_id, events in self._traces.items():
                        if all(e.start_time < cutoff_time for e in events):
                            traces_to_remove.append(trace_id)
                    
                    for trace_id in traces_to_remove:
                        del self._traces[trace_id]
                
                # Clean up state transitions
                self._state_transitions = [
                    t for t in self._state_transitions
                    if datetime.fromisoformat(t["timestamp"]) >= cutoff_time
                ]
                
                logger.debug("Completed monitoring data cleanup")
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.WARNING,
                    context={"component": "cleanup_loop"}
                )
    
    async def _check_alert_rules(self):
        """Check all alert rules and trigger alerts if necessary."""
        current_time = datetime.now()
        
        for rule in self._alert_rules:
            if not rule.enabled:
                continue
            
            # Check cooldown period
            if (rule.last_triggered and 
                current_time - rule.last_triggered < timedelta(minutes=rule.cooldown_minutes)):
                continue
            
            # Evaluate rule condition
            if await self._evaluate_alert_condition(rule):
                await self._trigger_alert(rule)
                rule.last_triggered = current_time
    
    async def _evaluate_alert_condition(self, rule: AlertRule) -> bool:
        """Evaluate an alert rule condition."""
        try:
            # Simple condition evaluation for common cases
            if "error_rate" in rule.condition:
                error_rate = self._get_recent_error_rate()
                return error_rate > rule.threshold_value
            
            elif "avg_duration" in rule.condition:
                avg_duration = self._get_average_response_time()
                return avg_duration > rule.threshold_value
            
            elif "memory_usage" in rule.condition:
                # Would integrate with resource manager
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to evaluate alert condition: {e}")
            return False
    
    async def _trigger_alert(self, rule: AlertRule):
        """Trigger an alert."""
        alert = {
            "id": str(uuid.uuid4()),
            "rule_name": rule.name,
            "level": rule.level.value,
            "condition": rule.condition,
            "threshold": rule.threshold_value,
            "timestamp": datetime.now().isoformat(),
            "metadata": await self._get_alert_context()
        }
        
        self._triggered_alerts.append(alert)
        
        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
        
        logger.warning(f"Alert triggered: {rule.name} - {rule.condition}")
    
    def _setup_default_alert_rules(self):
        """Setup default alert rules."""
        self._alert_rules = [
            AlertRule(
                name="High Error Rate",
                condition="error_rate > 0.1",
                level=AlertLevel.WARNING,
                threshold_value=0.1,
                time_window_minutes=5
            ),
            AlertRule(
                name="Critical Error Rate",
                condition="error_rate > 0.25",
                level=AlertLevel.CRITICAL,
                threshold_value=0.25,
                time_window_minutes=5
            ),
            AlertRule(
                name="High Response Time",
                condition="avg_duration > 5000",
                level=AlertLevel.WARNING,
                threshold_value=5000,
                time_window_minutes=5
            )
        ]
    
    def _get_recent_error_count(self) -> int:
        """Get count of recent errors."""
        cutoff_time = datetime.now() - timedelta(minutes=5)
        return len([
            m for m in self._metrics
            if m.name.endswith(".error") and m.timestamp >= cutoff_time
        ])
    
    def _get_recent_error_rate(self) -> float:
        """Get recent error rate."""
        total_operations = sum(m.total_calls for m in self._performance_metrics.values())
        total_errors = sum(m.failed_calls for m in self._performance_metrics.values())
        
        return total_errors / total_operations if total_operations > 0 else 0.0
    
    def _get_average_response_time(self) -> float:
        """Get average response time across all operations."""
        if not self._performance_metrics:
            return 0.0
        
        total_duration = sum(m.average_duration_ms for m in self._performance_metrics.values())
        return total_duration / len(self._performance_metrics)
    
    async def _get_alert_context(self) -> Dict[str, Any]:
        """Get context information for alerts."""
        return {
            "system_health": self.get_system_health(),
            "active_operations": len(self._active_spans),
            "recent_errors": self._get_recent_error_count()
        } 