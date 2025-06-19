"""
LangGraph Workflows Module

Contains StateGraph implementations for multi-agent workflow orchestration.
"""

from .commands import AgentCommand, CommandInterface, WorkflowCommand

# Use lazy imports to avoid circular dependencies
from .state_models import AgentState, CampaignPlanningState


def get_supervisor_workflow():
    """Lazy loader for SupervisorWorkflow to avoid circular imports."""
    from .supervisor import SupervisorWorkflow

    return SupervisorWorkflow


__all__ = [
    "get_supervisor_workflow",
    "AgentState",
    "CampaignPlanningState",
    "CommandInterface",
    "AgentCommand",
    "WorkflowCommand",
]
