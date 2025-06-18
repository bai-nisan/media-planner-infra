"""
Temporal Workflows for LangGraph Multi-Agent System

Provides workflow definitions for executing agent tasks and coordinating
multi-agent workflows via Temporal's durable execution model.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from app.services.langgraph.config import AgentType
from app.services.langgraph.workflows.supervisor import SupervisorWorkflow
from app.temporal.activities.agent_activities import (
    execute_agent_task_activity,
    get_agent_health_activity,
    execute_supervisor_workflow_activity
)

logger = logging.getLogger(__name__)


@workflow.defn
class AgentTaskWorkflow:
    """
    Workflow for executing individual agent tasks with retry logic and monitoring.
    
    This workflow provides durable execution for agent tasks, with automatic
    retries, timeout handling, and state persistence via Temporal.
    """
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an agent task with monitoring and error handling.
        
        Args:
            input_data: Task input containing agent_type, task_data, and context
            
        Returns:
            Dict containing task execution results
        """
        workflow.logger.info(f"Starting agent task workflow: {workflow.info().workflow_id}")
        
        try:
            # Extract task parameters
            agent_type = input_data.get("agent_type")
            task_data = input_data.get("task_data", {})
            context = input_data.get("context", {})
            
            # Validate required parameters
            if not agent_type:
                raise ApplicationError("agent_type is required")
            
            # Set up retry policy for agent execution
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=60),
                maximum_attempts=3,
                backoff_coefficient=2.0
            )
            
            # Execute the agent task with retry policy
            result = await workflow.execute_activity(
                execute_agent_task_activity,
                args=[agent_type, task_data, context],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy
            )
            
            workflow.logger.info(f"Agent task completed successfully: {workflow.info().workflow_id}")
            
            return {
                "success": True,
                "workflow_id": workflow.info().workflow_id,
                "agent_type": agent_type,
                "result": result,
                "completed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Agent task workflow failed: {e}")
            
            return {
                "success": False,
                "workflow_id": workflow.info().workflow_id,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }


@workflow.defn
class MultiAgentWorkflow:
    """
    Workflow for coordinating multiple agents through the LangGraph StateGraph.
    
    This workflow orchestrates complex multi-agent interactions using the
    SupervisorWorkflow and provides durable execution for long-running
    campaign planning workflows.
    """
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a multi-agent workflow using the LangGraph StateGraph.
        
        Args:
            input_data: Workflow input containing type, data, and configuration
            
        Returns:
            Dict containing workflow execution results
        """
        workflow.logger.info(f"Starting multi-agent workflow: {workflow.info().workflow_id}")
        
        try:
            # Extract workflow parameters
            workflow_type = input_data.get("workflow_type", "campaign_planning")
            workflow_input_data = input_data.get("input_data", {})
            config = input_data.get("config", {})
            tenant_id = input_data.get("tenant_id")
            user_id = input_data.get("user_id")
            
            # Validate required parameters
            if not tenant_id:
                raise ApplicationError("tenant_id is required for multi-agent workflows")
            
            # Set up retry policy for workflow execution
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(minutes=2),
                maximum_attempts=3,
                backoff_coefficient=2.0
            )
            
            # Prepare workflow state with tenant and user context
            workflow_state = {
                "workflow_type": workflow_type,
                "input_data": workflow_input_data,
                "config": config,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "workflow_id": workflow.info().workflow_id,
                "started_at": datetime.utcnow().isoformat()
            }
            
            # Execute the supervisor workflow via activity
            result = await workflow.execute_activity(
                execute_supervisor_workflow_activity,
                args=[workflow_state],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=retry_policy
            )
            
            workflow.logger.info(f"Multi-agent workflow completed: {workflow.info().workflow_id}")
            
            return {
                "success": True,
                "workflow_id": workflow.info().workflow_id,
                "workflow_type": workflow_type,
                "result": result,
                "tenant_id": tenant_id,
                "completed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Multi-agent workflow failed: {e}")
            
            return {
                "success": False,
                "workflow_id": workflow.info().workflow_id,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }


@workflow.defn
class AgentHealthMonitorWorkflow:
    """
    Workflow for monitoring agent health and performing maintenance tasks.
    
    This workflow runs periodically to check agent health, clean up resources,
    and ensure the multi-agent system is operating correctly.
    """
    
    @workflow.run
    async def run(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Monitor agent health and perform maintenance.
        
        Args:
            config: Optional configuration for health monitoring
            
        Returns:
            Dict containing health check results
        """
        workflow.logger.info("Starting agent health monitor workflow")
        
        try:
            # Set up retry policy for health checks
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=2,
                backoff_coefficient=2.0
            )
            
            # Check health of all agents
            health_results = await workflow.execute_activity(
                get_agent_health_activity,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            # Determine if any maintenance actions are needed
            maintenance_actions = []
            if health_results.get("healthy_agents", 0) < health_results.get("total_agents", 0):
                maintenance_actions.append("restart_unhealthy_agents")
            
            # Schedule maintenance if needed
            if maintenance_actions:
                workflow.logger.info(f"Scheduling maintenance actions: {maintenance_actions}")
                # Here you could trigger additional workflows for maintenance
            
            workflow.logger.info("Agent health monitor completed successfully")
            
            return {
                "success": True,
                "health_results": health_results,
                "maintenance_actions": maintenance_actions,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            workflow.logger.error(f"Agent health monitor failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            } 