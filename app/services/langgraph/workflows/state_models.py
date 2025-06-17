"""
State Models for LangGraph Multi-Agent Workflows

Defines the shared state structure used across agents in the StateGraph.
"""

import logging
from typing import Dict, Any, List, Optional, Annotated
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from langgraph.graph import MessagesState
from langchain.schema import BaseMessage

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """Stages in the campaign planning workflow."""
    WORKSPACE_ANALYSIS = "workspace_analysis"
    PLANNING = "planning"
    INSIGHTS_GENERATION = "insights_generation"
    SUPERVISOR_REVIEW = "supervisor_review"
    COMPLETE = "complete"
    ERROR = "error"


class AgentRole(str, Enum):
    """Agent roles in the multi-agent system."""
    WORKSPACE = "workspace"
    PLANNING = "planning"
    INSIGHTS = "insights"
    SUPERVISOR = "supervisor"


class TaskStatus(str, Enum):
    """Status of individual tasks within the workflow."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTask(BaseModel):
    """Individual task assigned to an agent."""
    id: str
    agent_role: AgentRole
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceData(BaseModel):
    """Data extracted from workspace sources."""
    google_sheets_data: Optional[Dict[str, Any]] = None
    drive_files: List[Dict[str, Any]] = Field(default_factory=list)
    campaign_data: Optional[Dict[str, Any]] = None
    validation_results: Optional[Dict[str, Any]] = None
    extraction_errors: List[str] = Field(default_factory=list)


class CampaignPlan(BaseModel):
    """Campaign planning results."""
    budget_allocation: Optional[Dict[str, Any]] = None
    channel_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    targeting_strategy: Optional[Dict[str, Any]] = None
    timeline: Optional[Dict[str, Any]] = None
    kpis: List[Dict[str, Any]] = Field(default_factory=list)
    risk_assessment: Optional[Dict[str, Any]] = None


class InsightsData(BaseModel):
    """Insights and analysis results."""
    performance_metrics: Optional[Dict[str, Any]] = None
    trend_analysis: Optional[Dict[str, Any]] = None
    optimization_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    competitive_analysis: Optional[Dict[str, Any]] = None
    predictive_insights: Optional[Dict[str, Any]] = None


class AgentState(MessagesState):
    """
    Enhanced state model that extends LangGraph's MessagesState
    for multi-agent coordination.
    """
    
    # Workflow coordination
    current_stage: WorkflowStage = WorkflowStage.WORKSPACE_ANALYSIS
    next_agent: Optional[AgentRole] = None
    active_tasks: List[AgentTask] = Field(default_factory=list)
    completed_tasks: List[AgentTask] = Field(default_factory=list)
    failed_tasks: List[AgentTask] = Field(default_factory=list)
    
    # Agent communication
    agent_messages: Dict[AgentRole, List[BaseMessage]] = Field(default_factory=dict)
    agent_results: Dict[AgentRole, Dict[str, Any]] = Field(default_factory=dict)
    agent_errors: Dict[AgentRole, List[str]] = Field(default_factory=dict)
    
    # Business context
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    
    # Data containers
    workspace_data: WorkspaceData = Field(default_factory=WorkspaceData)
    campaign_plan: CampaignPlan = Field(default_factory=CampaignPlan)
    insights_data: InsightsData = Field(default_factory=InsightsData)
    
    # Workflow metadata
    workflow_start_time: datetime = Field(default_factory=datetime.now)
    last_activity_time: datetime = Field(default_factory=datetime.now)
    execution_context: Dict[str, Any] = Field(default_factory=dict)
    
    # Configuration
    workflow_config: Dict[str, Any] = Field(default_factory=dict)
    agent_configs: Dict[AgentRole, Dict[str, Any]] = Field(default_factory=dict)
    
    def add_agent_message(self, agent_role: AgentRole, message: BaseMessage):
        """Add a message from a specific agent."""
        if agent_role not in self.agent_messages:
            self.agent_messages[agent_role] = []
        self.agent_messages[agent_role].append(message)
        self.last_activity_time = datetime.now()
    
    def set_agent_result(self, agent_role: AgentRole, result: Dict[str, Any]):
        """Set the result from a specific agent."""
        self.agent_results[agent_role] = result
        self.last_activity_time = datetime.now()
    
    def add_agent_error(self, agent_role: AgentRole, error: str):
        """Add an error from a specific agent."""
        if agent_role not in self.agent_errors:
            self.agent_errors[agent_role] = []
        self.agent_errors[agent_role].append(error)
        self.last_activity_time = datetime.now()
    
    def transition_to_stage(self, stage: WorkflowStage, next_agent: Optional[AgentRole] = None):
        """Transition the workflow to a new stage."""
        self.current_stage = stage
        self.next_agent = next_agent
        self.last_activity_time = datetime.now()
        
        logger.info(f"Workflow transitioned to stage: {stage.value}")
        if next_agent:
            logger.info(f"Next agent: {next_agent.value}")
    
    def add_task(self, task: AgentTask):
        """Add a new task to the active tasks."""
        self.active_tasks.append(task)
        self.last_activity_time = datetime.now()
    
    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None):
        """Mark a task as completed."""
        for i, task in enumerate(self.active_tasks):
            if task.id == task_id:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                completed_task = self.active_tasks.pop(i)
                self.completed_tasks.append(completed_task)
                self.last_activity_time = datetime.now()
                break
    
    def fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        for i, task in enumerate(self.active_tasks):
            if task.id == task_id:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.now()
                failed_task = self.active_tasks.pop(i)
                self.failed_tasks.append(failed_task)
                self.last_activity_time = datetime.now()
                break
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get a summary of the current workflow state."""
        return {
            "current_stage": self.current_stage.value,
            "next_agent": self.next_agent.value if self.next_agent else None,
            "active_tasks_count": len(self.active_tasks),
            "completed_tasks_count": len(self.completed_tasks),
            "failed_tasks_count": len(self.failed_tasks),
            "workflow_duration": (datetime.now() - self.workflow_start_time).total_seconds(),
            "last_activity": self.last_activity_time.isoformat(),
            "has_errors": bool(self.agent_errors)
        }


# Type alias for the main state used in the StateGraph
CampaignPlanningState = AgentState 