"""
Supervisor Workflow for LangGraph Multi-Agent System

Implements the StateGraph and orchestrates the multi-agent workflow for
intelligent campaign planning using LangGraph's StateGraph and Command patterns.
"""

import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain.schema import BaseMessage, HumanMessage, SystemMessage

from .state_models import (
    AgentState, CampaignPlanningState, AgentRole, WorkflowStage, 
    AgentTask, TaskStatus
)
from .commands import (
    CommandInterface, AgentHandoffCommand, DataRequestCommand,
    TaskAssignmentCommand, ResultDeliveryCommand, WorkflowControlCommand,
    create_command, CommandType
)
# NOTE: Removed circular import - agents will be injected
# from ..agents import WorkspaceAgent, PlanningAgent, InsightsAgent, SupervisorAgent

logger = logging.getLogger(__name__)


class SupervisorWorkflow:
    """
    Main workflow orchestrator using LangGraph's StateGraph pattern.
    Coordinates the multi-agent system for campaign planning.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.graph: Optional[StateGraph] = None
        self.compiled_graph = None
        self.agents: Dict[AgentRole, Any] = {}
        self.command_queue: List[CommandInterface] = []
        self.execution_history: List[Dict[str, Any]] = []
        
        # Initialize the workflow (agents will be injected later)
        self._initialize_agents()
        self._build_state_graph()
    
    def _initialize_agents(self):
        """Initialize all agents for the workflow."""
        try:
            # Initialize agents with their configurations
            # These would typically be injected via dependency injection
            self.agents = {
                AgentRole.WORKSPACE: None,  # Will be injected
                AgentRole.PLANNING: None,   # Will be injected
                AgentRole.INSIGHTS: None,   # Will be injected
                AgentRole.SUPERVISOR: None  # Will be injected
            }
            logger.info("Agents initialized for SupervisorWorkflow")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise
    
    def set_agents(self, agents: Dict[AgentRole, Any]):
        """Set the agents for the workflow."""
        self.agents.update(agents)
        logger.info(f"Agents set: {list(agents.keys())}")
    
    def _build_state_graph(self):
        """Build the StateGraph for the multi-agent workflow."""
        try:
            # Create the StateGraph with our custom state
            self.graph = StateGraph(CampaignPlanningState)
            
            # Add nodes for each agent
            self.graph.add_node("workspace_agent", self._workspace_node)
            self.graph.add_node("planning_agent", self._planning_node)
            self.graph.add_node("insights_agent", self._insights_node)
            self.graph.add_node("supervisor_agent", self._supervisor_node)
            self.graph.add_node("workflow_complete", self._completion_node)
            
            # Define the workflow edges with conditional routing
            self.graph.add_edge(START, "workspace_agent")
            
            # Add conditional edges for dynamic routing
            self.graph.add_conditional_edges(
                "workspace_agent",
                self._route_from_workspace,
                {
                    "planning": "planning_agent",
                    "supervisor": "supervisor_agent",
                    "error": END
                }
            )
            
            self.graph.add_conditional_edges(
                "planning_agent",
                self._route_from_planning,
                {
                    "insights": "insights_agent",
                    "workspace": "workspace_agent",
                    "supervisor": "supervisor_agent",
                    "error": END
                }
            )
            
            self.graph.add_conditional_edges(
                "insights_agent",
                self._route_from_insights,
                {
                    "supervisor": "supervisor_agent",
                    "planning": "planning_agent",
                    "error": END
                }
            )
            
            self.graph.add_conditional_edges(
                "supervisor_agent",
                self._route_from_supervisor,
                {
                    "workspace": "workspace_agent",
                    "planning": "planning_agent",
                    "insights": "insights_agent",
                    "complete": "workflow_complete",
                    "error": END
                }
            )
            
            self.graph.add_edge("workflow_complete", END)
            
            # Compile the graph
            self.compiled_graph = self.graph.compile()
            logger.info("StateGraph built and compiled successfully")
            
        except Exception as e:
            logger.error(f"Failed to build StateGraph: {e}")
            raise
    
    # Node implementations for each agent
    async def _workspace_node(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Process workspace analysis tasks."""
        try:
            logger.info("Executing workspace_agent node")
            
            # Update workflow stage
            state.transition_to_stage(WorkflowStage.WORKSPACE_ANALYSIS, AgentRole.WORKSPACE)
            
            # Simulate workspace processing
            # In real implementation, this would call the actual WorkspaceAgent
            workspace_results = {
                "google_sheets_parsed": True,
                "campaign_data_extracted": True,
                "validation_passed": True,
                "data_quality_score": 0.95
            }
            
            # Store results in state
            state.workspace_data.google_sheets_data = workspace_results
            state.set_agent_result(AgentRole.WORKSPACE, workspace_results)
            
            # Add completion message
            completion_msg = HumanMessage(
                content="Workspace analysis completed successfully",
                additional_kwargs={
                    "agent": AgentRole.WORKSPACE.value,
                    "results": workspace_results,
                    "stage": WorkflowStage.WORKSPACE_ANALYSIS.value
                }
            )
            state.messages.append(completion_msg)
            
            return {"workspace_status": "completed", "results": workspace_results}
            
        except Exception as e:
            logger.error(f"Workspace node execution failed: {e}")
            state.add_agent_error(AgentRole.WORKSPACE, str(e))
            state.transition_to_stage(WorkflowStage.ERROR)
            return {"workspace_status": "error", "error": str(e)}
    
    async def _planning_node(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Process campaign planning tasks."""
        try:
            logger.info("Executing planning_agent node")
            
            # Update workflow stage
            state.transition_to_stage(WorkflowStage.PLANNING, AgentRole.PLANNING)
            
            # Simulate planning processing
            planning_results = {
                "budget_allocated": True,
                "channels_selected": ["google_ads", "facebook_ads", "display"],
                "target_audience_defined": True,
                "timeline_created": True,
                "kpis_established": True
            }
            
            # Store results in state
            state.campaign_plan.budget_allocation = planning_results
            state.set_agent_result(AgentRole.PLANNING, planning_results)
            
            # Add completion message
            completion_msg = HumanMessage(
                content="Campaign planning completed successfully",
                additional_kwargs={
                    "agent": AgentRole.PLANNING.value,
                    "results": planning_results,
                    "stage": WorkflowStage.PLANNING.value
                }
            )
            state.messages.append(completion_msg)
            
            return {"planning_status": "completed", "results": planning_results}
            
        except Exception as e:
            logger.error(f"Planning node execution failed: {e}")
            state.add_agent_error(AgentRole.PLANNING, str(e))
            state.transition_to_stage(WorkflowStage.ERROR)
            return {"planning_status": "error", "error": str(e)}
    
    async def _insights_node(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Process insights generation tasks."""
        try:
            logger.info("Executing insights_agent node")
            
            # Update workflow stage
            state.transition_to_stage(WorkflowStage.INSIGHTS_GENERATION, AgentRole.INSIGHTS)
            
            # Simulate insights processing
            insights_results = {
                "performance_analyzed": True,
                "trends_identified": ["increasing_mobile_traffic", "seasonal_variation"],
                "optimization_recommendations": [
                    {"type": "budget_reallocation", "priority": "high"},
                    {"type": "audience_expansion", "priority": "medium"}
                ],
                "risk_assessment": {"overall_score": 0.8, "risks": ["market_volatility"]}
            }
            
            # Store results in state
            state.insights_data.performance_metrics = insights_results
            state.set_agent_result(AgentRole.INSIGHTS, insights_results)
            
            # Add completion message
            completion_msg = HumanMessage(
                content="Insights generation completed successfully",
                additional_kwargs={
                    "agent": AgentRole.INSIGHTS.value,
                    "results": insights_results,
                    "stage": WorkflowStage.INSIGHTS_GENERATION.value
                }
            )
            state.messages.append(completion_msg)
            
            return {"insights_status": "completed", "results": insights_results}
            
        except Exception as e:
            logger.error(f"Insights node execution failed: {e}")
            state.add_agent_error(AgentRole.INSIGHTS, str(e))
            state.transition_to_stage(WorkflowStage.ERROR)
            return {"insights_status": "error", "error": str(e)}
    
    async def _supervisor_node(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Process supervisor review and coordination tasks."""
        try:
            logger.info("Executing supervisor_agent node")
            
            # Update workflow stage
            state.transition_to_stage(WorkflowStage.SUPERVISOR_REVIEW, AgentRole.SUPERVISOR)
            
            # Supervisor logic to determine next steps
            supervisor_results = {
                "workflow_reviewed": True,
                "quality_check": "passed",
                "next_action": self._determine_next_action(state),
                "completion_score": self._calculate_completion_score(state)
            }
            
            # Store results in state
            state.set_agent_result(AgentRole.SUPERVISOR, supervisor_results)
            
            # Add completion message
            completion_msg = HumanMessage(
                content=f"Supervisor review completed: {supervisor_results['next_action']}",
                additional_kwargs={
                    "agent": AgentRole.SUPERVISOR.value,
                    "results": supervisor_results,
                    "stage": WorkflowStage.SUPERVISOR_REVIEW.value
                }
            )
            state.messages.append(completion_msg)
            
            return {"supervisor_status": "completed", "results": supervisor_results}
            
        except Exception as e:
            logger.error(f"Supervisor node execution failed: {e}")
            state.add_agent_error(AgentRole.SUPERVISOR, str(e))
            state.transition_to_stage(WorkflowStage.ERROR)
            return {"supervisor_status": "error", "error": str(e)}
    
    async def _completion_node(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Handle workflow completion."""
        try:
            logger.info("Executing workflow completion node")
            
            # Update workflow stage
            state.transition_to_stage(WorkflowStage.COMPLETE)
            
            # Generate final summary
            final_results = {
                "workflow_completed": True,
                "completion_time": datetime.now().isoformat(),
                "summary": state.get_workflow_summary(),
                "final_outputs": {
                    "workspace_data": state.workspace_data.dict() if state.workspace_data else {},
                    "campaign_plan": state.campaign_plan.dict() if state.campaign_plan else {},
                    "insights_data": state.insights_data.dict() if state.insights_data else {}
                }
            }
            
            # Add final message
            final_msg = HumanMessage(
                content="Multi-agent workflow completed successfully",
                additional_kwargs={
                    "workflow_summary": final_results,
                    "stage": WorkflowStage.COMPLETE.value
                }
            )
            state.messages.append(final_msg)
            
            logger.info("Workflow completed successfully")
            return final_results
            
        except Exception as e:
            logger.error(f"Completion node execution failed: {e}")
            state.transition_to_stage(WorkflowStage.ERROR)
            return {"completion_status": "error", "error": str(e)}
    
    # Routing functions for conditional edges
    def _route_from_workspace(self, state: CampaignPlanningState) -> Literal["planning", "supervisor", "error"]:
        """Determine routing from workspace agent."""
        if state.current_stage == WorkflowStage.ERROR:
            return "error"
        
        # Check if workspace processing was successful
        workspace_results = state.agent_results.get(AgentRole.WORKSPACE, {})
        if workspace_results.get("validation_passed", False):
            return "planning"
        else:
            return "supervisor"  # Need supervisor intervention
    
    def _route_from_planning(self, state: CampaignPlanningState) -> Literal["insights", "workspace", "supervisor", "error"]:
        """Determine routing from planning agent."""
        if state.current_stage == WorkflowStage.ERROR:
            return "error"
        
        # Check planning results and determine next step
        planning_results = state.agent_results.get(AgentRole.PLANNING, {})
        if planning_results.get("budget_allocated", False):
            return "insights"
        else:
            return "supervisor"  # Need supervisor review
    
    def _route_from_insights(self, state: CampaignPlanningState) -> Literal["supervisor", "planning", "error"]:
        """Determine routing from insights agent."""
        if state.current_stage == WorkflowStage.ERROR:
            return "error"
        
        # Insights always go to supervisor for final review
        return "supervisor"
    
    def _route_from_supervisor(self, state: CampaignPlanningState) -> Literal["workspace", "planning", "insights", "complete", "error"]:
        """Determine routing from supervisor agent."""
        if state.current_stage == WorkflowStage.ERROR:
            return "error"
        
        # Get supervisor's decision
        supervisor_results = state.agent_results.get(AgentRole.SUPERVISOR, {})
        next_action = supervisor_results.get("next_action", "complete")
        
        if next_action == "complete":
            return "complete"
        elif next_action == "retry_workspace":
            return "workspace"
        elif next_action == "retry_planning":
            return "planning"
        elif next_action == "retry_insights":
            return "insights"
        else:
            return "complete"
    
    def _determine_next_action(self, state: CampaignPlanningState) -> str:
        """Determine the next action based on current workflow state."""
        completion_score = self._calculate_completion_score(state)
        
        if completion_score >= 0.9:
            return "complete"
        elif completion_score >= 0.7:
            # Check if we need additional insights
            if not state.insights_data.performance_metrics:
                return "retry_insights"
            return "complete"
        elif completion_score >= 0.5:
            # Check if planning needs improvement
            if not state.campaign_plan.budget_allocation:
                return "retry_planning"
            return "retry_insights"
        else:
            # Low completion score, restart from workspace
            return "retry_workspace"
    
    def _calculate_completion_score(self, state: CampaignPlanningState) -> float:
        """Calculate workflow completion score."""
        score = 0.0
        total_checks = 0
        
        # Check workspace completion
        if state.workspace_data.google_sheets_data:
            score += 0.3
        total_checks += 0.3
        
        # Check planning completion
        if state.campaign_plan.budget_allocation:
            score += 0.4
        total_checks += 0.4
        
        # Check insights completion
        if state.insights_data.performance_metrics:
            score += 0.3
        total_checks += 0.3
        
        return score / total_checks if total_checks > 0 else 0.0
    
    # Command execution methods
    async def execute_command(self, command: CommandInterface, state: CampaignPlanningState) -> Dict[str, Any]:
        """Execute a command within the workflow context."""
        try:
            logger.info(f"Executing command: {command.command_type.value}")
            
            # Add command to execution history
            self.execution_history.append({
                "command_id": command.command_id,
                "command_type": command.command_type.value,
                "timestamp": datetime.now().isoformat()
            })
            
            # Execute the command
            result = await command.execute(state)
            
            logger.info(f"Command executed successfully: {command.command_id}")
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise
    
    async def handoff_to_agent(
        self,
        target_agent: AgentRole,
        source_agent: AgentRole,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        state: Optional[CampaignPlanningState] = None
    ) -> Dict[str, Any]:
        """Create and execute a handoff command."""
        command = AgentHandoffCommand(
            target_agent=target_agent,
            source_agent=source_agent,
            handoff_message=message,
            handoff_data=data
        )
        
        if state:
            return await self.execute_command(command, state)
        else:
            # Queue the command for later execution
            self.command_queue.append(command)
            return {"command_queued": True, "command_id": command.command_id}
    
    # Main execution methods
    async def run_workflow(
        self,
        initial_state: Optional[CampaignPlanningState] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the complete multi-agent workflow."""
        try:
            logger.info("Starting multi-agent workflow execution")
            
            # Initialize state if not provided
            if initial_state is None:
                initial_state = CampaignPlanningState()
            
            # Set workflow configuration
            if config:
                initial_state.workflow_config = config
            
            # Execute the compiled graph
            if not self.compiled_graph:
                raise ValueError("Workflow graph not compiled")
            
            # Run the workflow
            final_state = await self.compiled_graph.ainvoke(initial_state)
            
            logger.info("Multi-agent workflow completed successfully")
            
            return {
                "workflow_completed": True,
                "final_state": final_state,
                "execution_summary": final_state.get_workflow_summary(),
                "execution_history": self.execution_history
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status and metrics."""
        return {
            "graph_compiled": self.compiled_graph is not None,
            "agents_configured": len([a for a in self.agents.values() if a is not None]),
            "total_agents": len(self.agents),
            "commands_in_queue": len(self.command_queue),
            "execution_history_length": len(self.execution_history),
            "last_updated": datetime.now().isoformat()
        } 