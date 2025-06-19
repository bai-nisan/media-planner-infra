"""
Base Agent class for LangGraph Multi-Agent System
Enhanced with advanced state management, error handling, and monitoring
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.types import Command

from .config import AgentConfig, AgentType
from .state_manager import StateManager, StateOperationType
from .error_handler import ErrorHandler, ErrorSeverity, ErrorCategory, RetryConfig
from .resource_manager import ResourceManager, ResourceType
from .monitoring import MonitoringService, MetricType
from .workflows.state_models import AgentRole

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system with enhanced capabilities."""
    
    def __init__(
        self, 
        config: AgentConfig, 
        supabase_client=None,
        state_manager: Optional[StateManager] = None,
        error_handler: Optional[ErrorHandler] = None,
        resource_manager: Optional[ResourceManager] = None,
        monitoring: Optional[MonitoringService] = None
    ):
        self.config = config
        self.supabase_client = supabase_client
        
        # Handle both string and enum types for config.type
        agent_type_str = config.type.value if hasattr(config.type, 'value') else str(config.type)
        self.agent_id = f"{agent_type_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Enhanced management components
        self.state_manager = state_manager or StateManager(supabase_client)
        self.error_handler = error_handler or ErrorHandler()
        self.resource_manager = resource_manager or ResourceManager(error_handler=self.error_handler)
        self.monitoring = monitoring or MonitoringService(error_handler=self.error_handler)
        
        # Agent role mapping
        self.agent_role = self._get_agent_role()
        
        # Initialize LLM with error handling
        self.llm = ChatOpenAI(
            model_name=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Register circuit breaker for LLM calls
        self.llm_circuit_breaker = self.error_handler.create_circuit_breaker(
            name=f"llm_{self.agent_id}",
            config=None  # Use defaults
        )
        
        logger.info(f"Initialized {config.name} with ID: {self.agent_id}")
        
        # Update monitoring
        self.monitoring.update_agent_status(
            self.agent_role, 
            "healthy", 
            {"agent_id": self.agent_id, "initialization_time": datetime.now().isoformat()}
        )
    
    def _get_agent_role(self) -> AgentRole:
        """Map AgentType to AgentRole."""
        # Import AgentType here to handle the mapping
        from .config import AgentType
        
        # Handle both string and enum types for config.type
        if isinstance(self.config.type, str):
            # Convert string to AgentType enum
            try:
                agent_type = AgentType(self.config.type)
            except ValueError:
                # If string doesn't match any enum value, default to SUPERVISOR
                logger.warning(f"Unknown agent type: {self.config.type}, defaulting to SUPERVISOR")
                agent_type = AgentType.SUPERVISOR
        else:
            agent_type = self.config.type
        
        mapping = {
            AgentType.WORKSPACE: AgentRole.WORKSPACE,
            AgentType.PLANNING: AgentRole.PLANNING,
            AgentType.INSIGHTS: AgentRole.INSIGHTS,
            AgentType.SUPERVISOR: AgentRole.SUPERVISOR
        }
        return mapping.get(agent_type, AgentRole.SUPERVISOR)
    
    @abstractmethod
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize agent-specific tools."""
        pass
    
    @abstractmethod
    async def process_task(self, state: MessagesState, task: Dict[str, Any]) -> Command:
        """Process a task and return a command for routing."""
        pass
    
    async def _call_llm(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the LLM with messages using enhanced error handling and monitoring."""
        operation_name = f"llm_call_{self.agent_role.value}"
        
        async with self.resource_manager.acquire_resource(
            ResourceType.NETWORK_CONNECTIONS, 
            f"llm_{self.agent_id}_{int(datetime.now().timestamp())}"
        ):
            with self.monitoring.trace_operation(
                operation_name,
                agent_role=self.agent_role,
                metadata={"message_count": len(messages)}
            ) as span_id:
                try:
                    # Add system prompt if not already present
                    if not any(isinstance(msg, SystemMessage) for msg in messages):
                        messages = [SystemMessage(content=self.config.system_prompt)] + messages
                    
                    # Use circuit breaker for LLM calls
                    response = await self.llm_circuit_breaker.call(
                        self.llm.ainvoke, messages
                    )
                    
                    # Record successful call
                    self.monitoring.increment_counter(
                        f"{operation_name}.success",
                        tags={"agent_id": self.agent_id}
                    )
                    
                    return response
                    
                except Exception as e:
                    # Handle error with enhanced error handling
                    await self.error_handler.handle_error(
                        e,
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.EXTERNAL_API,
                        context={
                            "agent_id": self.agent_id,
                            "agent_role": self.agent_role.value,
                            "operation": operation_name,
                            "message_count": len(messages)
                        }
                    )
                    
                    # Record failed call
                    self.monitoring.increment_counter(
                        f"{operation_name}.error",
                        tags={"agent_id": self.agent_id, "error_type": type(e).__name__}
                    )
                    
                    # Update agent status
                    self.monitoring.update_agent_status(
                        self.agent_role,
                        "degraded",
                        {"last_error": str(e), "error_time": datetime.now().isoformat()}
                    )
                    
                    raise
    
    async def _save_state(
        self, 
        state_data: Dict[str, Any], 
        tenant_id: Optional[str] = None,
        create_checkpoint: bool = True
    ) -> bool:
        """Save agent state using enhanced StateManager."""
        operation_name = f"state_save_{self.agent_role.value}"
        
        with self.monitoring.time_operation(operation_name):
            try:
                # Convert to AgentState if it's a dictionary
                if isinstance(state_data, dict):
                    from .state_models import AgentState
                    agent_state = AgentState(**state_data)
                else:
                    agent_state = state_data
                
                success = await self.state_manager.save_state(
                    state_id=self.agent_id,
                    state_data=agent_state,
                    tenant_id=tenant_id,
                    agent_role=self.agent_role,
                    create_checkpoint=create_checkpoint
                )
                
                if success:
                    logger.debug(f"Saved state for {self.config.name}")
                    self.monitoring.increment_counter(
                        f"{operation_name}.success",
                        tags={"agent_id": self.agent_id}
                    )
                else:
                    logger.warning(f"Failed to save state for {self.config.name}")
                    self.monitoring.increment_counter(
                        f"{operation_name}.failure",
                        tags={"agent_id": self.agent_id}
                    )
                
                return success
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.DATABASE,
                    context={
                        "agent_id": self.agent_id,
                        "operation": operation_name
                    }
                )
                return False
    
    async def _load_state(self, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load agent state using enhanced StateManager."""
        operation_name = f"state_load_{self.agent_role.value}"
        
        with self.monitoring.time_operation(operation_name):
            try:
                agent_state = await self.state_manager.load_state(
                    state_id=self.agent_id,
                    tenant_id=tenant_id
                )
                
                if agent_state:
                    logger.debug(f"Loaded state for {self.config.name}")
                    self.monitoring.increment_counter(
                        f"{operation_name}.success",
                        tags={"agent_id": self.agent_id}
                    )
                    return agent_state.dict() if hasattr(agent_state, 'dict') else agent_state
                else:
                    logger.debug(f"No state found for {self.config.name}")
                    self.monitoring.increment_counter(
                        f"{operation_name}.not_found",
                        tags={"agent_id": self.agent_id}
                    )
                    return None
                
            except Exception as e:
                await self.error_handler.handle_error(
                    e,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATABASE,
                    context={
                        "agent_id": self.agent_id,
                        "operation": operation_name
                    }
                )
                return None
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Any]:
        """Get a tool by name."""
        return self.tools.get(tool_name)
    
    def list_available_tools(self) -> List[str]:
        """List all available tools for this agent."""
        return list(self.tools.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check for the agent."""
        # Handle both string and enum types for config.type
        agent_type_str = self.config.type.value if hasattr(self.config.type, 'value') else str(self.config.type)
        
        health_data = {
            "agent_id": self.agent_id,
            "agent_type": agent_type_str,
            "agent_role": self.agent_role.value,
            "tools_count": len(self.tools),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Test LLM connectivity with timeout
            async with self.resource_manager.acquire_resource(
                ResourceType.NETWORK_CONNECTIONS,
                f"health_check_{self.agent_id}",
                timeout=10.0
            ):
                test_message = HumanMessage(content="Health check")
                await self._call_llm([test_message])
            
            # Get additional health metrics
            health_data.update({
                "status": "healthy",
                "llm_circuit_breaker_state": self.llm_circuit_breaker.state.value,
                "circuit_breaker_failures": self.llm_circuit_breaker.failure_count,
                "resource_manager_active": self.resource_manager._is_monitoring,
                "monitoring_active": self.monitoring._is_monitoring,
                "state_manager_metrics": await self._get_state_manager_health()
            })
            
            # Update monitoring
            self.monitoring.update_agent_status(
                self.agent_role,
                "healthy",
                {"health_check_time": datetime.now().isoformat()}
            )
            
            return health_data
            
        except Exception as e:
            # Handle health check failure
            await self.error_handler.handle_error(
                e,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.SYSTEM,
                context={
                    "agent_id": self.agent_id,
                    "operation": "health_check"
                }
            )
            
            health_data.update({
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__,
                "llm_circuit_breaker_state": self.llm_circuit_breaker.state.value,
                "circuit_breaker_failures": self.llm_circuit_breaker.failure_count
            })
            
            # Update monitoring
            self.monitoring.update_agent_status(
                self.agent_role,
                "unhealthy",
                {"error": str(e), "error_time": datetime.now().isoformat()}
            )
            
            return health_data
    
    async def _get_state_manager_health(self) -> Dict[str, Any]:
        """Get health metrics from state manager."""
        try:
            return await self.state_manager.get_system_metrics()
        except Exception as e:
            logger.warning(f"Failed to get state manager health: {e}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Clean up agent resources."""
        try:
            # Stop monitoring services
            if hasattr(self.resource_manager, 'stop_monitoring'):
                await self.resource_manager.stop_monitoring()
            
            if hasattr(self.monitoring, 'stop_monitoring'):
                await self.monitoring.stop_monitoring()
            
            # Update status
            self.monitoring.update_agent_status(
                self.agent_role,
                "shutdown",
                {"shutdown_time": datetime.now().isoformat()}
            )
            
            logger.info(f"Agent {self.agent_id} cleaned up successfully")
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.SYSTEM,
                context={"agent_id": self.agent_id, "operation": "cleanup"}
            ) 