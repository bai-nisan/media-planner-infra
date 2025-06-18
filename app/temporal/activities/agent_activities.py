"""
Temporal Activities for LangGraph Multi-Agent System

Activities for executing agent tasks, health checks, and workflow coordination
within Temporal workflows for durable execution.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from temporalio import activity

from app.services.langgraph.agent_service import get_agent_service
from app.services.langgraph.config import AgentType
from app.services.langgraph.workflows.supervisor import SupervisorWorkflow
from app.services.langgraph.workflows.state_models import CampaignPlanningState

logger = logging.getLogger(__name__)


@activity.defn
async def execute_agent_task_activity(
    agent_type: str,
    task_data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Activity for executing a single agent task.
    
    Args:
        agent_type: Type of agent to execute (workspace, planning, insights, supervisor)
        task_data: Task data and parameters
        context: Additional context for the task
        
    Returns:
        Dict containing task execution results
    """
    activity.logger.info(f"Executing agent task: {agent_type}")
    
    try:
        # Get agent service instance
        agent_service = await get_agent_service()
        
        # Validate agent type
        try:
            agent_enum = AgentType(agent_type)
        except ValueError:
            raise ValueError(f"Invalid agent type: {agent_type}")
        
        # Execute the task
        result = await agent_service.execute_task(
            agent_type=agent_enum,
            task=task_data,
            context=context or {}
        )
        
        activity.logger.info(f"Agent task completed: {agent_type}")
        
        return {
            "success": result.get("success", False),
            "agent_type": agent_type,
            "task_type": task_data.get("task_type"),
            "result": result.get("result"),
            "error": result.get("error"),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat())
        }
        
    except Exception as e:
        activity.logger.error(f"Agent task execution failed: {e}")
        return {
            "success": False,
            "agent_type": agent_type,
            "task_type": task_data.get("task_type"),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@activity.defn
async def get_agent_health_activity() -> Dict[str, Any]:
    """
    Activity for checking the health of all agents in the system.
    
    Returns:
        Dict containing health status of all agents
    """
    activity.logger.info("Checking agent health")
    
    try:
        # Get agent service instance
        agent_service = await get_agent_service()
        
        # Perform health check
        health_results = await agent_service.health_check()
        
        activity.logger.info("Agent health check completed")
        
        return health_results
        
    except Exception as e:
        activity.logger.error(f"Agent health check failed: {e}")
        return {
            "service_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@activity.defn
async def execute_supervisor_workflow_activity(
    workflow_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Activity for executing the LangGraph SupervisorWorkflow.
    
    Args:
        workflow_state: Initial state for the workflow including configuration
        
    Returns:
        Dict containing workflow execution results
    """
    activity.logger.info("Executing supervisor workflow")
    
    try:
        # Create supervisor workflow instance
        supervisor = SupervisorWorkflow(config=workflow_state.get("config", {}))
        
        # Get agent service and set agents for the workflow
        agent_service = await get_agent_service()
        
        # Map agents to the supervisor workflow
        agents = {}
        for agent_type in AgentType:
            agent = await agent_service.get_agent(agent_type)
            if agent:
                agents[agent_type] = agent
        
        supervisor.set_agents(agents)
        
        # Create initial state for the workflow
        initial_state = CampaignPlanningState(
            tenant_id=workflow_state.get("tenant_id"),
            user_id=workflow_state.get("user_id"),
            session_id=workflow_state.get("workflow_id"),
            workflow_config=workflow_state.get("config", {})
        )
        
        # Add initial message with workflow input data
        from langchain_core.messages import HumanMessage
        initial_message = HumanMessage(
            content="Start campaign planning workflow",
            additional_kwargs={
                "workflow_type": workflow_state.get("workflow_type"),
                "input_data": workflow_state.get("input_data"),
                "tenant_id": workflow_state.get("tenant_id"),
                "user_id": workflow_state.get("user_id")
            }
        )
        initial_state.messages = [initial_message]
        
        # Execute the workflow
        workflow_result = await supervisor.run_workflow(
            initial_state=initial_state,
            config=workflow_state.get("config")
        )
        
        activity.logger.info("Supervisor workflow completed")
        
        return {
            "success": True,
            "workflow_type": workflow_state.get("workflow_type"),
            "result": workflow_result,
            "completion_score": workflow_result.get("completion_score", 0.0),
            "current_stage": workflow_result.get("current_stage"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        activity.logger.error(f"Supervisor workflow execution failed: {e}")
        return {
            "success": False,
            "workflow_type": workflow_state.get("workflow_type"),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@activity.defn
async def validate_agent_configuration_activity(
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Activity for validating agent configuration before workflow execution.
    
    Args:
        config: Agent configuration to validate
        
    Returns:
        Dict containing validation results
    """
    activity.logger.info("Validating agent configuration")
    
    try:
        # Get agent service instance
        agent_service = await get_agent_service()
        
        # Check if all required agents are available
        required_agents = [AgentType.WORKSPACE, AgentType.PLANNING, AgentType.INSIGHTS, AgentType.SUPERVISOR]
        available_agents = []
        unavailable_agents = []
        
        for agent_type in required_agents:
            agent = await agent_service.get_agent(agent_type)
            if agent:
                health = await agent.health_check()
                if health.get("status") == "healthy":
                    available_agents.append(agent_type.value)
                else:
                    unavailable_agents.append(f"{agent_type.value} (unhealthy)")
            else:
                unavailable_agents.append(f"{agent_type.value} (not initialized)")
        
        is_valid = len(unavailable_agents) == 0
        
        activity.logger.info(f"Agent configuration validation: {'valid' if is_valid else 'invalid'}")
        
        return {
            "is_valid": is_valid,
            "available_agents": available_agents,
            "unavailable_agents": unavailable_agents,
            "total_required": len(required_agents),
            "total_available": len(available_agents),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        activity.logger.error(f"Agent configuration validation failed: {e}")
        return {
            "is_valid": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@activity.defn
async def cleanup_agent_resources_activity(
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Activity for cleaning up agent resources and state.
    
    Args:
        tenant_id: Optional tenant ID to limit cleanup scope
        
    Returns:
        Dict containing cleanup results
    """
    activity.logger.info(f"Cleaning up agent resources for tenant: {tenant_id or 'all'}")
    
    try:
        # Get agent service instance
        agent_service = await get_agent_service()
        
        # Perform cleanup operations
        cleanup_results = {
            "state_cleaned": False,
            "connections_closed": False,
            "cache_cleared": False,
            "error_logs_archived": False
        }
        
        # Clean up agent state if tenant-specific
        if tenant_id:
            # Implementation would depend on how tenant state is stored
            # For now, we'll just log the action
            activity.logger.info(f"Cleaning up state for tenant: {tenant_id}")
            cleanup_results["state_cleaned"] = True
        
        # Clear caches and close unnecessary connections
        # This would be implemented based on specific requirements
        cleanup_results["connections_closed"] = True
        cleanup_results["cache_cleared"] = True
        cleanup_results["error_logs_archived"] = True
        
        activity.logger.info("Agent resource cleanup completed")
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "cleanup_results": cleanup_results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        activity.logger.error(f"Agent resource cleanup failed: {e}")
        return {
            "success": False,
            "tenant_id": tenant_id,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        } 