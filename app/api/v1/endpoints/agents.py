"""
LangGraph Multi-Agent System API Endpoints

FastAPI routes for managing and executing tasks with the LangGraph multi-agent system.
Provides endpoints for agent health checks, task execution, and workflow management.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.dependencies import get_temporal_service, get_tenant_id, get_user_id
from app.services.langgraph.agent_service import AgentService, get_agent_service
from app.services.langgraph.config import AgentType
from app.services.langgraph.workflows.supervisor import SupervisorWorkflow
from app.services.temporal_service import TemporalService

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request/response schemas
class AgentTaskRequest(BaseModel):
    """Request model for agent task execution."""

    task_type: str = Field(..., description="Type of task to execute")
    agent_type: str = Field(
        ..., description="Target agent type (workspace, planning, insights, supervisor)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Task data and parameters"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context for the task"
    )
    async_execution: bool = Field(
        default=False, description="Whether to execute task asynchronously via Temporal"
    )
    priority: str = Field(
        default="medium", description="Task priority (low, medium, high)"
    )


class AgentTaskResponse(BaseModel):
    """Response model for agent task execution."""

    task_id: str = Field(..., description="Unique task identifier")
    success: bool = Field(..., description="Whether the task completed successfully")
    agent_type: str = Field(..., description="Agent that processed the task")
    task_type: str = Field(..., description="Type of task executed")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Task execution result"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if task failed"
    )
    timestamp: str = Field(..., description="Task completion timestamp")
    execution_time_ms: Optional[int] = Field(
        default=None, description="Execution time in milliseconds"
    )


class WorkflowRequest(BaseModel):
    """Request model for workflow execution."""

    workflow_type: str = Field(
        default="campaign_planning", description="Type of workflow to execute"
    )
    input_data: Dict[str, Any] = Field(..., description="Initial data for the workflow")
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Workflow configuration"
    )
    tenant_specific: bool = Field(
        default=True, description="Whether this is tenant-specific"
    )


class WorkflowResponse(BaseModel):
    """Response model for workflow execution."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    status: str = Field(..., description="Workflow status")
    current_stage: str = Field(..., description="Current workflow stage")
    results: Optional[Dict[str, Any]] = Field(
        default=None, description="Workflow results"
    )
    completion_score: Optional[float] = Field(
        default=None, description="Workflow completion score (0-1)"
    )
    created_at: str = Field(..., description="Workflow creation timestamp")


class AgentHealthResponse(BaseModel):
    """Response model for agent health status."""

    service_status: str = Field(..., description="Overall service status")
    agents: Dict[str, Dict[str, Any]] = Field(
        ..., description="Individual agent health status"
    )
    total_agents: int = Field(..., description="Total number of agents")
    healthy_agents: int = Field(..., description="Number of healthy agents")
    timestamp: str = Field(..., description="Health check timestamp")


@router.get("/health", response_model=AgentHealthResponse)
async def get_agents_health(
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentHealthResponse:
    """
    Get health status for all agents in the system.

    Returns comprehensive health information including individual agent status,
    system-level health, and diagnostic information.
    """
    try:
        health_data = await agent_service.health_check()
        return AgentHealthResponse(**health_data)
    except Exception as e:
        logger.error(f"Failed to get agent health: {e}")
        raise HTTPException(
            status_code=503, detail=f"Agent health check failed: {str(e)}"
        )


@router.get("/", response_model=Dict[str, Any])
async def list_agents(
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    List all available agents and their current status.

    Returns information about each agent including name, description,
    status, and capabilities.
    """
    try:
        agents_list = await agent_service.list_agents()
        return {
            "agents": agents_list,
            "total_count": len(agents_list),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve agent list: {str(e)}"
        )


@router.post("/execute", response_model=AgentTaskResponse)
async def execute_agent_task(
    request: AgentTaskRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    user_id: Optional[str] = Depends(get_user_id),
    agent_service: AgentService = Depends(get_agent_service),
    temporal_service: TemporalService = Depends(get_temporal_service),
) -> AgentTaskResponse:
    """
    Execute a task using a specific agent.

    Supports both synchronous and asynchronous execution via Temporal workflows.
    For long-running tasks, use async_execution=True to leverage Temporal.
    """
    try:
        # Validate agent type
        try:
            agent_type = AgentType(request.agent_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent type: {request.agent_type}. Valid types: {[e.value for e in AgentType]}",
            )

        # Prepare task data with tenant and user context
        task_data = {
            **request.data,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "task_type": request.task_type,
            "priority": request.priority,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Generate unique task ID
        task_id = (
            f"task_{agent_type.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        )

        if request.async_execution:
            # Execute via Temporal workflow for long-running tasks
            workflow_id = f"agent_task_{task_id}"

            # Start Temporal workflow
            workflow_handle = await temporal_service.start_workflow(
                workflow_id=workflow_id,
                workflow_type="agent_task_workflow",
                args=[
                    {
                        "agent_type": agent_type.value,
                        "task_data": task_data,
                        "context": request.context or {},
                    }
                ],
                task_queue="agent-tasks",
            )

            return AgentTaskResponse(
                task_id=task_id,
                success=True,
                agent_type=agent_type.value,
                task_type=request.task_type,
                result={
                    "workflow_id": workflow_id,
                    "status": "started",
                    "message": "Task started asynchronously via Temporal",
                },
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            # Execute synchronously
            start_time = datetime.utcnow()

            result = await agent_service.execute_task(
                agent_type=agent_type, task=task_data, context=request.context
            )

            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            return AgentTaskResponse(
                task_id=task_id,
                success=result.get("success", False),
                agent_type=agent_type.value,
                task_type=request.task_type,
                result=result.get("result"),
                error=result.get("error"),
                timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
                execution_time_ms=execution_time_ms,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute agent task: {e}")
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


@router.post("/workflow", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    user_id: Optional[str] = Depends(get_user_id),
    temporal_service: TemporalService = Depends(get_temporal_service),
) -> WorkflowResponse:
    """
    Execute a complete multi-agent workflow.

    Orchestrates multiple agents through a coordinated workflow using the
    LangGraph StateGraph implementation via Temporal workflows.
    """
    try:
        # Generate unique workflow ID
        workflow_id = f"workflow_{request.workflow_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

        # Prepare workflow input data
        workflow_input = {
            "workflow_type": request.workflow_type,
            "input_data": request.input_data,
            "config": request.config or {},
            "tenant_id": tenant_id,
            "user_id": user_id,
            "tenant_specific": request.tenant_specific,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Start Temporal workflow for multi-agent coordination
        workflow_handle = await temporal_service.start_workflow(
            workflow_id=workflow_id,
            workflow_type="multi_agent_workflow",
            args=[workflow_input],
            task_queue="agent-workflows",
        )

        # For now, return started status - in production you might want to wait for initial results
        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
            current_stage="initialization",
            results={
                "message": "Multi-agent workflow started successfully",
                "temporal_workflow_id": workflow_id,
            },
            created_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        raise HTTPException(
            status_code=500, detail=f"Workflow execution failed: {str(e)}"
        )


@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(
    workflow_id: str, temporal_service: TemporalService = Depends(get_temporal_service)
) -> Dict[str, Any]:
    """
    Get the current status of a running workflow.

    Returns workflow execution status, current stage, and any available results.
    """
    try:
        # Get workflow status from Temporal
        workflow_status = await temporal_service.get_workflow_status(workflow_id)

        return {
            "workflow_id": workflow_id,
            "status": workflow_status.get("status", "unknown"),
            "current_stage": workflow_status.get("current_stage"),
            "results": workflow_status.get("results"),
            "completion_score": workflow_status.get("completion_score"),
            "error": workflow_status.get("error"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve workflow status: {str(e)}"
        )


@router.get("/{agent_type}/health")
async def get_agent_health(
    agent_type: str, agent_service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    """
    Get health status for a specific agent.

    Returns detailed health information for the specified agent type.
    """
    try:
        # Validate agent type
        try:
            agent_enum = AgentType(agent_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent type: {agent_type}. Valid types: {[e.value for e in AgentType]}",
            )

        agent = await agent_service.get_agent(agent_enum)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_type} not found or not initialized",
            )

        health_status = await agent.health_check()
        return {
            "agent_type": agent_type,
            "health": health_status,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent health for {agent_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed for agent {agent_type}: {str(e)}",
        )
