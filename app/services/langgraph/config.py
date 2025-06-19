"""
Configuration for LangGraph Multi-Agent System
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent types in the multi-agent system."""

    WORKSPACE = "workspace"
    PLANNING = "planning"
    INSIGHTS = "insights"
    SUPERVISOR = "supervisor"


class AgentConfig(BaseModel):
    """Configuration for individual agents."""

    name: str
    type: AgentType
    description: str
    model_name: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 2000
    tools: List[str] = Field(default_factory=list)
    system_prompt: str = ""

    class Config:
        use_enum_values = True


class LangGraphConfig(BaseModel):
    """Main configuration for LangGraph multi-agent system."""

    # Agent configurations
    agents: Dict[AgentType, AgentConfig] = Field(default_factory=dict)

    # Workflow configuration
    max_iterations: int = 10
    timeout_seconds: int = 300

    # State persistence
    enable_persistence: bool = True
    state_store_table: str = "agent_states"

    # Logging
    log_level: str = "INFO"
    enable_tracing: bool = True

    def __init__(self, **data):
        super().__init__(**data)
        self._setup_default_agents()

    def _setup_default_agents(self) -> None:
        """Set up default agent configurations."""

        # Workspace Agent
        self.agents[AgentType.WORKSPACE] = AgentConfig(
            name="WorkspaceAgent",
            type=AgentType.WORKSPACE,
            description="Handles Google Sheet parsing, data extraction, and workspace management",
            model_name="gpt-4-turbo-preview",
            temperature=0.3,
            tools=[
                "google_sheets_reader",
                "file_parser",
                "data_validator",
                "workspace_manager",
            ],
            system_prompt="""You are the Workspace Agent responsible for managing data extraction and workspace operations.
            
Your primary responsibilities:
- Parse and extract data from Google Sheets
- Validate data integrity and format
- Manage file operations and workspace structure
- Handle data transformations for downstream agents

Always ensure data quality and provide detailed validation reports.""",
        )

        # Planning Agent
        self.agents[AgentType.PLANNING] = AgentConfig(
            name="PlanningAgent",
            type=AgentType.PLANNING,
            description="Develops campaign strategies, budget allocations, and planning recommendations",
            model_name="gpt-4-turbo-preview",
            temperature=0.5,
            tools=[
                "budget_optimizer",
                "campaign_planner",
                "strategy_generator",
                "performance_predictor",
            ],
            system_prompt="""You are the Planning Agent responsible for developing intelligent campaign strategies.

Your primary responsibilities:
- Analyze campaign requirements and objectives
- Develop optimal budget allocation strategies
- Generate campaign recommendations
- Predict performance outcomes
- Create detailed implementation plans

Always provide data-driven recommendations with clear reasoning.""",
        )

        # Insights Agent
        self.agents[AgentType.INSIGHTS] = AgentConfig(
            name="InsightsAgent",
            type=AgentType.INSIGHTS,
            description="Analyzes performance data and generates actionable insights",
            model_name="gpt-4-turbo-preview",
            temperature=0.4,
            tools=[
                "data_analyzer",
                "trend_detector",
                "performance_evaluator",
                "insight_generator",
            ],
            system_prompt="""You are the Insights Agent responsible for data analysis and insight generation.

Your primary responsibilities:
- Analyze campaign performance data
- Identify trends and patterns
- Generate actionable insights
- Provide optimization recommendations
- Create detailed reports

Always provide clear, actionable insights with supporting data.""",
        )

        # Supervisor Agent
        self.agents[AgentType.SUPERVISOR] = AgentConfig(
            name="SupervisorAgent",
            type=AgentType.SUPERVISOR,
            description="Orchestrates workflow and coordinates communication between agents",
            model_name="gpt-4-turbo-preview",
            temperature=0.2,
            tools=[
                "task_coordinator",
                "agent_communicator",
                "workflow_manager",
                "decision_maker",
            ],
            system_prompt="""You are the Supervisor Agent responsible for orchestrating the multi-agent workflow.

Your primary responsibilities:
- Coordinate tasks between agents
- Make routing decisions
- Monitor agent performance
- Handle conflicts and errors
- Ensure workflow completion

Always maintain clear communication and efficient task allocation.""",
        )
