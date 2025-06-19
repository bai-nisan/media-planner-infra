"""
Command Patterns for LangGraph Multi-Agent Communication

Implements the Command design pattern for inter-agent communication,
allowing for flexible, decoupled agent interactions.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from .state_models import AgentRole, AgentState, AgentTask, TaskStatus, WorkflowStage

logger = logging.getLogger(__name__)


class CommandType(str, Enum):
    """Types of commands for agent communication."""

    HANDOFF = "handoff"
    DATA_REQUEST = "data_request"
    TASK_ASSIGNMENT = "task_assignment"
    RESULT_DELIVERY = "result_delivery"
    ERROR_NOTIFICATION = "error_notification"
    WORKFLOW_CONTROL = "workflow_control"
    VALIDATION_REQUEST = "validation_request"


class CommandPriority(str, Enum):
    """Priority levels for commands."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandInterface(ABC):
    """Abstract base class for all commands."""

    def __init__(
        self,
        command_id: str = None,
        command_type: CommandType = CommandType.HANDOFF,
        priority: CommandPriority = CommandPriority.MEDIUM,
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.command_id = command_id or str(uuid.uuid4())
        self.command_type = command_type
        self.priority = priority
        self.timeout = timeout
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.executed_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.status = "pending"
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

    @abstractmethod
    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the command with the given state."""
        pass

    @abstractmethod
    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo the command execution if possible."""
        pass

    def can_execute(self, state: AgentState) -> bool:
        """Check if the command can be executed in the current state."""
        return True

    def get_command_info(self) -> Dict[str, Any]:
        """Get information about the command."""
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "priority": self.priority.value,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "metadata": self.metadata,
            "has_error": bool(self.error),
        }


class AgentHandoffCommand(CommandInterface):
    """Command for handing off workflow control to another agent."""

    def __init__(
        self,
        target_agent: AgentRole,
        source_agent: AgentRole,
        handoff_message: str,
        handoff_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(command_type=CommandType.HANDOFF, **kwargs)
        self.target_agent = target_agent
        self.source_agent = source_agent
        self.handoff_message = handoff_message
        self.handoff_data = handoff_data or {}

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the handoff command."""
        try:
            self.executed_at = datetime.now()
            self.status = "executing"

            # Log the handoff
            logger.info(
                f"Agent handoff: {self.source_agent.value} -> {self.target_agent.value}"
            )

            # Update state with handoff information
            state.next_agent = self.target_agent

            # Add handoff message to the state
            handoff_msg = HumanMessage(
                content=f"Handoff from {self.source_agent.value}: {self.handoff_message}",
                additional_kwargs={
                    "command_id": self.command_id,
                    "handoff_data": self.handoff_data,
                    "source_agent": self.source_agent.value,
                    "target_agent": self.target_agent.value,
                },
            )

            state.add_agent_message(self.target_agent, handoff_msg)

            # Determine next workflow stage based on target agent
            stage_mapping = {
                AgentRole.WORKSPACE: WorkflowStage.WORKSPACE_ANALYSIS,
                AgentRole.PLANNING: WorkflowStage.PLANNING,
                AgentRole.INSIGHTS: WorkflowStage.INSIGHTS_GENERATION,
                AgentRole.SUPERVISOR: WorkflowStage.SUPERVISOR_REVIEW,
            }

            if self.target_agent in stage_mapping:
                state.transition_to_stage(
                    stage_mapping[self.target_agent], self.target_agent
                )

            self.status = "completed"
            self.completed_at = datetime.now()
            self.result = {
                "target_agent": self.target_agent.value,
                "handoff_successful": True,
                "handoff_time": self.completed_at.isoformat(),
            }

            return self.result

        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.completed_at = datetime.now()
            logger.error(f"Handoff command failed: {e}")
            raise

    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo the handoff (return control to source agent)."""
        state.next_agent = self.source_agent
        return {"handoff_undone": True, "returned_to": self.source_agent.value}


class DataRequestCommand(CommandInterface):
    """Command for requesting data from another agent."""

    def __init__(
        self,
        target_agent: AgentRole,
        source_agent: AgentRole,
        data_request: str,
        request_params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(command_type=CommandType.DATA_REQUEST, **kwargs)
        self.target_agent = target_agent
        self.source_agent = source_agent
        self.data_request = data_request
        self.request_params = request_params or {}

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the data request command."""
        try:
            self.executed_at = datetime.now()
            self.status = "executing"

            # Create data request message
            request_msg = HumanMessage(
                content=f"Data request from {self.source_agent.value}: {self.data_request}",
                additional_kwargs={
                    "command_id": self.command_id,
                    "request_params": self.request_params,
                    "source_agent": self.source_agent.value,
                    "request_type": "data_request",
                },
            )

            state.add_agent_message(self.target_agent, request_msg)

            self.status = "completed"
            self.completed_at = datetime.now()
            self.result = {
                "request_sent": True,
                "target_agent": self.target_agent.value,
                "request_id": self.command_id,
            }

            return self.result

        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.completed_at = datetime.now()
            logger.error(f"Data request command failed: {e}")
            raise

    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo data request (cancel the request)."""
        # Remove the request from target agent's messages if possible
        return {"request_cancelled": True}


class TaskAssignmentCommand(CommandInterface):
    """Command for assigning a task to an agent."""

    def __init__(
        self,
        target_agent: AgentRole,
        task_description: str,
        task_params: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(command_type=CommandType.TASK_ASSIGNMENT, **kwargs)
        self.target_agent = target_agent
        self.task_description = task_description
        self.task_params = task_params or {}
        self.dependencies = dependencies or []

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the task assignment command."""
        try:
            self.executed_at = datetime.now()
            self.status = "executing"

            # Create agent task
            task = AgentTask(
                id=self.command_id,
                agent_role=self.target_agent,
                description=self.task_description,
                dependencies=self.dependencies,
                metadata=self.task_params,
            )

            state.add_task(task)

            # Create task assignment message
            assignment_msg = HumanMessage(
                content=f"Task assigned: {self.task_description}",
                additional_kwargs={
                    "command_id": self.command_id,
                    "task_id": task.id,
                    "task_params": self.task_params,
                    "dependencies": self.dependencies,
                    "assignment_type": "task_assignment",
                },
            )

            state.add_agent_message(self.target_agent, assignment_msg)

            self.status = "completed"
            self.completed_at = datetime.now()
            self.result = {
                "task_assigned": True,
                "task_id": task.id,
                "target_agent": self.target_agent.value,
            }

            return self.result

        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.completed_at = datetime.now()
            logger.error(f"Task assignment command failed: {e}")
            raise

    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo task assignment (cancel the task)."""
        # Remove task from active tasks
        state.active_tasks = [t for t in state.active_tasks if t.id != self.command_id]
        return {"task_cancelled": True}


class ResultDeliveryCommand(CommandInterface):
    """Command for delivering results from one agent to another."""

    def __init__(
        self,
        target_agent: AgentRole,
        source_agent: AgentRole,
        result_data: Dict[str, Any],
        result_summary: str,
        **kwargs,
    ):
        super().__init__(command_type=CommandType.RESULT_DELIVERY, **kwargs)
        self.target_agent = target_agent
        self.source_agent = source_agent
        self.result_data = result_data
        self.result_summary = result_summary

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the result delivery command."""
        try:
            self.executed_at = datetime.now()
            self.status = "executing"

            # Store result in state
            state.set_agent_result(self.source_agent, self.result_data)

            # Create result delivery message
            result_msg = AIMessage(
                content=f"Results from {self.source_agent.value}: {self.result_summary}",
                additional_kwargs={
                    "command_id": self.command_id,
                    "result_data": self.result_data,
                    "source_agent": self.source_agent.value,
                    "delivery_type": "result_delivery",
                },
            )

            state.add_agent_message(self.target_agent, result_msg)

            self.status = "completed"
            self.completed_at = datetime.now()
            self.result = {
                "result_delivered": True,
                "target_agent": self.target_agent.value,
                "source_agent": self.source_agent.value,
            }

            return self.result

        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.completed_at = datetime.now()
            logger.error(f"Result delivery command failed: {e}")
            raise

    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo result delivery (not typically possible)."""
        return {"result_delivery_undo": "not_supported"}


class WorkflowControlCommand(CommandInterface):
    """Command for controlling workflow progression."""

    def __init__(
        self,
        control_action: str,  # "pause", "resume", "reset", "complete"
        control_params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(command_type=CommandType.WORKFLOW_CONTROL, **kwargs)
        self.control_action = control_action
        self.control_params = control_params or {}

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the workflow control command."""
        try:
            self.executed_at = datetime.now()
            self.status = "executing"

            if self.control_action == "complete":
                state.transition_to_stage(WorkflowStage.COMPLETE)
            elif self.control_action == "reset":
                state.transition_to_stage(
                    WorkflowStage.WORKSPACE_ANALYSIS, AgentRole.WORKSPACE
                )
                state.active_tasks = []
                state.failed_tasks = []
            elif self.control_action == "pause":
                state.execution_context["paused"] = True
                state.execution_context["pause_time"] = datetime.now().isoformat()
            elif self.control_action == "resume":
                state.execution_context["paused"] = False
                state.execution_context["resume_time"] = datetime.now().isoformat()

            self.status = "completed"
            self.completed_at = datetime.now()
            self.result = {
                "control_action": self.control_action,
                "action_successful": True,
            }

            return self.result

        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.completed_at = datetime.now()
            logger.error(f"Workflow control command failed: {e}")
            raise

    async def undo(self, state: AgentState) -> Dict[str, Any]:
        """Undo workflow control action."""
        return {"workflow_control_undo": "implementation_dependent"}


# Factory function for creating commands
def create_command(command_type: CommandType, **kwargs) -> CommandInterface:
    """Factory function to create commands of different types."""

    command_map = {
        CommandType.HANDOFF: AgentHandoffCommand,
        CommandType.DATA_REQUEST: DataRequestCommand,
        CommandType.TASK_ASSIGNMENT: TaskAssignmentCommand,
        CommandType.RESULT_DELIVERY: ResultDeliveryCommand,
        CommandType.WORKFLOW_CONTROL: WorkflowControlCommand,
    }

    if command_type not in command_map:
        raise ValueError(f"Unknown command type: {command_type}")

    return command_map[command_type](**kwargs)


# Aliases for common command patterns
AgentCommand = CommandInterface
WorkflowCommand = WorkflowControlCommand
