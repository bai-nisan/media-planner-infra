"""
Agent Service for LangGraph Multi-Agent System

Main service class that coordinates and manages all agents.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings
from app.services.database import get_supabase_client

from .config import LangGraphConfig, AgentType
from .agents import WorkspaceAgent, PlanningAgent, InsightsAgent, SupervisorAgent


logger = logging.getLogger(__name__)


class AgentService:
    """Main service for managing the multi-agent system."""
    
    def __init__(self, config: Optional[LangGraphConfig] = None):
        self.config = config or LangGraphConfig()
        self.supabase_client = None
        self.agents: Dict[AgentType, Any] = {}
        self.is_initialized = False
        
        logger.info("Initialized AgentService")
    
    async def initialize(self) -> None:
        """Initialize the agent service and all agents."""
        try:
            # Initialize Supabase client for state persistence
            if self.config.enable_persistence:
                self.supabase_client = await get_supabase_client()
                logger.info("Connected to Supabase for agent state persistence")
            
            # Initialize all agents
            await self._initialize_agents()
            
            self.is_initialized = True
            logger.info("AgentService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentService: {e}")
            raise
    
    async def _initialize_agents(self) -> None:
        """Initialize all agents with their configurations."""
        try:
            # Initialize Workspace Agent
            workspace_config = self.config.agents[AgentType.WORKSPACE]
            self.agents[AgentType.WORKSPACE] = WorkspaceAgent(
                config=workspace_config,
                supabase_client=self.supabase_client
            )
            
            # TODO: Initialize other agents when implemented
            # planning_config = self.config.agents[AgentType.PLANNING]
            # self.agents[AgentType.PLANNING] = PlanningAgent(
            #     config=planning_config,
            #     supabase_client=self.supabase_client
            # )
            
            # insights_config = self.config.agents[AgentType.INSIGHTS]
            # self.agents[AgentType.INSIGHTS] = InsightsAgent(
            #     config=insights_config,
            #     supabase_client=self.supabase_client
            # )
            
            # supervisor_config = self.config.agents[AgentType.SUPERVISOR]
            # self.agents[AgentType.SUPERVISOR] = SupervisorAgent(
            #     config=supervisor_config,
            #     supabase_client=self.supabase_client
            # )
            
            logger.info(f"Initialized {len(self.agents)} agents")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise
    
    async def get_agent(self, agent_type: AgentType) -> Optional[Any]:
        """Get an agent by type."""
        if not self.is_initialized:
            await self.initialize()
        
        return self.agents.get(agent_type)
    
    async def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all available agents and their status."""
        if not self.is_initialized:
            await self.initialize()
        
        agent_list = {}
        for agent_type, agent in self.agents.items():
            health_status = await agent.health_check()
            agent_list[agent_type.value] = {
                "name": agent.config.name,
                "description": agent.config.description,
                "status": health_status.get("status", "unknown"),
                "tools_count": len(agent.tools),
                "last_check": health_status.get("timestamp")
            }
        
        return agent_list
    
    async def execute_task(
        self, 
        agent_type: AgentType, 
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a task using a specific agent."""
        try:
            if not self.is_initialized:
                await self.initialize()
            
            agent = self.agents.get(agent_type)
            if not agent:
                raise ValueError(f"Agent type {agent_type.value} not available")
            
            # Prepare state for the agent
            state = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Execute task: {task.get('type', 'unknown')}",
                        "metadata": {
                            "task": task,
                            "context": context or {},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                ]
            }
            
            # Execute the task
            result = await agent.process_task(state, task)
            
            logger.info(f"Task executed successfully by {agent_type.value}")
            
            return {
                "success": True,
                "agent_type": agent_type.value,
                "task_type": task.get("type"),
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to execute task with {agent_type.value}: {e}")
            return {
                "success": False,
                "agent_type": agent_type.value,
                "task_type": task.get("type"),
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for the entire agent system."""
        try:
            if not self.is_initialized:
                await self.initialize()
            
            health_status = {
                "service_status": "healthy",
                "agents": {},
                "total_agents": len(self.agents),
                "healthy_agents": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Check each agent
            for agent_type, agent in self.agents.items():
                agent_health = await agent.health_check()
                health_status["agents"][agent_type.value] = agent_health
                
                if agent_health.get("status") == "healthy":
                    health_status["healthy_agents"] += 1
            
            # Determine overall service status
            if health_status["healthy_agents"] == 0:
                health_status["service_status"] = "unhealthy"
            elif health_status["healthy_agents"] < health_status["total_agents"]:
                health_status["service_status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def shutdown(self) -> None:
        """Shutdown the agent service and cleanup resources."""
        try:
            logger.info("Shutting down AgentService")
            
            # Cleanup agents
            for agent_type, agent in self.agents.items():
                # Perform any agent-specific cleanup if needed
                logger.debug(f"Cleaning up {agent_type.value}")
            
            # Close Supabase connection if needed
            if self.supabase_client:
                # Supabase client cleanup is handled automatically
                logger.debug("Supabase client cleaned up")
            
            self.is_initialized = False
            logger.info("AgentService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during AgentService shutdown: {e}")


# Global instance
_agent_service: Optional[AgentService] = None


async def get_agent_service() -> AgentService:
    """Get the global agent service instance."""
    global _agent_service
    
    if _agent_service is None:
        _agent_service = AgentService()
        await _agent_service.initialize()
    
    return _agent_service 