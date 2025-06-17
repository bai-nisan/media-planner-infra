"""
Tests for StateGraph and Command Patterns

Tests the core workflow functionality including StateGraph transitions,
Command pattern execution, and agent communication.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from ..workflows.supervisor import SupervisorWorkflow
from ..workflows.state_models import (
    CampaignPlanningState, AgentRole, WorkflowStage, AgentTask, TaskStatus
)
from ..workflows.commands import (
    AgentHandoffCommand, DataRequestCommand, TaskAssignmentCommand,
    ResultDeliveryCommand, WorkflowControlCommand, create_command, CommandType
)


class TestStateGraphTransitions:
    """Test StateGraph transitions and routing logic."""
    
    @pytest.fixture
    def workflow(self):
        """Create a SupervisorWorkflow instance for testing."""
        return SupervisorWorkflow()
    
    @pytest.fixture
    def initial_state(self):
        """Create an initial state for testing."""
        return CampaignPlanningState()
    
    def test_workflow_initialization(self, workflow):
        """Test that the workflow initializes correctly."""
        assert workflow.graph is not None
        assert workflow.compiled_graph is not None
        assert len(workflow.agents) == 4
        assert AgentRole.WORKSPACE in workflow.agents
        assert AgentRole.PLANNING in workflow.agents
        assert AgentRole.INSIGHTS in workflow.agents
        assert AgentRole.SUPERVISOR in workflow.agents
    
    def test_workflow_status(self, workflow):
        """Test workflow status reporting."""
        status = workflow.get_workflow_status()
        
        assert status["graph_compiled"] is True
        assert status["total_agents"] == 4
        assert status["commands_in_queue"] == 0
        assert status["execution_history_length"] == 0
        assert "last_updated" in status
    
    def test_route_from_workspace_success(self, workflow, initial_state):
        """Test routing from workspace agent when successful."""
        # Set successful workspace results
        initial_state.set_agent_result(AgentRole.WORKSPACE, {"validation_passed": True})
        
        route = workflow._route_from_workspace(initial_state)
        assert route == "planning"
    
    def test_route_from_workspace_failure(self, workflow, initial_state):
        """Test routing from workspace agent when validation fails."""
        # Set failed workspace results
        initial_state.set_agent_result(AgentRole.WORKSPACE, {"validation_passed": False})
        
        route = workflow._route_from_workspace(initial_state)
        assert route == "supervisor"
    
    def test_route_from_planning_success(self, workflow, initial_state):
        """Test routing from planning agent when successful."""
        # Set successful planning results
        initial_state.set_agent_result(AgentRole.PLANNING, {"budget_allocated": True})
        
        route = workflow._route_from_planning(initial_state)
        assert route == "insights"
    
    def test_route_from_insights(self, workflow, initial_state):
        """Test routing from insights agent (always goes to supervisor)."""
        route = workflow._route_from_insights(initial_state)
        assert route == "supervisor"
    
    def test_route_from_supervisor_complete(self, workflow, initial_state):
        """Test routing from supervisor when workflow should complete."""
        # Set supervisor results indicating completion
        initial_state.set_agent_result(AgentRole.SUPERVISOR, {"next_action": "complete"})
        
        route = workflow._route_from_supervisor(initial_state)
        assert route == "complete"
    
    def test_route_from_supervisor_retry(self, workflow, initial_state):
        """Test routing from supervisor when retry is needed."""
        # Set supervisor results indicating retry
        initial_state.set_agent_result(AgentRole.SUPERVISOR, {"next_action": "retry_workspace"})
        
        route = workflow._route_from_supervisor(initial_state)
        assert route == "workspace"
    
    def test_completion_score_calculation(self, workflow, initial_state):
        """Test workflow completion score calculation."""
        # Initially should be 0
        score = workflow._calculate_completion_score(initial_state)
        assert score == 0.0
        
        # Add workspace data
        initial_state.workspace_data.google_sheets_data = {"test": "data"}
        score = workflow._calculate_completion_score(initial_state)
        assert score == 0.3
        
        # Add planning data
        initial_state.campaign_plan.budget_allocation = {"budget": 10000}
        score = workflow._calculate_completion_score(initial_state)
        assert score == 0.7
        
        # Add insights data
        initial_state.insights_data.performance_metrics = {"metrics": "data"}
        score = workflow._calculate_completion_score(initial_state)
        assert score == 1.0
    
    def test_determine_next_action(self, workflow, initial_state):
        """Test next action determination based on completion score."""
        # Low score should retry workspace
        action = workflow._determine_next_action(initial_state)
        assert action == "retry_workspace"
        
        # Medium score with missing planning should retry planning
        initial_state.workspace_data.google_sheets_data = {"test": "data"}
        action = workflow._determine_next_action(initial_state)
        assert action == "retry_planning"
        
        # High score should complete
        initial_state.campaign_plan.budget_allocation = {"budget": 10000}
        initial_state.insights_data.performance_metrics = {"metrics": "data"}
        action = workflow._determine_next_action(initial_state)
        assert action == "complete"


class TestCommandPatterns:
    """Test Command pattern implementations."""
    
    @pytest.fixture
    def state(self):
        """Create a state for command testing."""
        return CampaignPlanningState()
    
    @pytest.mark.asyncio
    async def test_handoff_command_execution(self, state):
        """Test agent handoff command execution."""
        command = AgentHandoffCommand(
            target_agent=AgentRole.PLANNING,
            source_agent=AgentRole.WORKSPACE,
            handoff_message="Workspace analysis complete, proceeding to planning"
        )
        
        result = await command.execute(state)
        
        assert result["handoff_successful"] is True
        assert result["target_agent"] == AgentRole.PLANNING.value
        assert state.next_agent == AgentRole.PLANNING
        assert state.current_stage == WorkflowStage.PLANNING
        assert len(state.agent_messages[AgentRole.PLANNING]) == 1
    
    @pytest.mark.asyncio
    async def test_data_request_command(self, state):
        """Test data request command execution."""
        command = DataRequestCommand(
            target_agent=AgentRole.WORKSPACE,
            source_agent=AgentRole.PLANNING,
            data_request="Need campaign historical data",
            request_params={"time_period": "last_6_months"}
        )
        
        result = await command.execute(state)
        
        assert result["request_sent"] is True
        assert result["target_agent"] == AgentRole.WORKSPACE.value
        assert len(state.agent_messages[AgentRole.WORKSPACE]) == 1
    
    @pytest.mark.asyncio
    async def test_task_assignment_command(self, state):
        """Test task assignment command execution."""
        command = TaskAssignmentCommand(
            target_agent=AgentRole.INSIGHTS,
            task_description="Analyze campaign performance metrics",
            task_params={"analysis_type": "performance", "priority": "high"}
        )
        
        result = await command.execute(state)
        
        assert result["task_assigned"] is True
        assert result["target_agent"] == AgentRole.INSIGHTS.value
        assert len(state.active_tasks) == 1
        assert state.active_tasks[0].description == "Analyze campaign performance metrics"
        assert state.active_tasks[0].agent_role == AgentRole.INSIGHTS
    
    @pytest.mark.asyncio
    async def test_result_delivery_command(self, state):
        """Test result delivery command execution."""
        result_data = {
            "analysis_complete": True,
            "key_findings": ["trend1", "trend2"],
            "recommendations": ["rec1", "rec2"]
        }
        
        command = ResultDeliveryCommand(
            target_agent=AgentRole.SUPERVISOR,
            source_agent=AgentRole.INSIGHTS,
            result_data=result_data,
            result_summary="Analysis completed with key insights identified"
        )
        
        result = await command.execute(state)
        
        assert result["result_delivered"] is True
        assert state.agent_results[AgentRole.INSIGHTS] == result_data
        assert len(state.agent_messages[AgentRole.SUPERVISOR]) == 1
    
    @pytest.mark.asyncio
    async def test_workflow_control_command(self, state):
        """Test workflow control commands."""
        # Test pause command
        pause_command = WorkflowControlCommand(
            control_action="pause"
        )
        
        result = await pause_command.execute(state)
        
        assert result["action_successful"] is True
        assert state.execution_context["paused"] is True
        
        # Test resume command
        resume_command = WorkflowControlCommand(
            control_action="resume"
        )
        
        result = await resume_command.execute(state)
        
        assert result["action_successful"] is True
        assert state.execution_context["paused"] is False
        
        # Test complete command
        complete_command = WorkflowControlCommand(
            control_action="complete"
        )
        
        result = await complete_command.execute(state)
        
        assert result["action_successful"] is True
        assert state.current_stage == WorkflowStage.COMPLETE
    
    def test_command_factory(self):
        """Test command factory function."""
        # Test handoff command creation
        handoff_cmd = create_command(
            CommandType.HANDOFF,
            target_agent=AgentRole.PLANNING,
            source_agent=AgentRole.WORKSPACE,
            handoff_message="Test handoff"
        )
        
        assert isinstance(handoff_cmd, AgentHandoffCommand)
        assert handoff_cmd.target_agent == AgentRole.PLANNING
        
        # Test task assignment command creation
        task_cmd = create_command(
            CommandType.TASK_ASSIGNMENT,
            target_agent=AgentRole.INSIGHTS,
            task_description="Test task"
        )
        
        assert isinstance(task_cmd, TaskAssignmentCommand)
        assert task_cmd.target_agent == AgentRole.INSIGHTS
        
        # Test invalid command type
        with pytest.raises(ValueError):
            create_command("invalid_type")
    
    def test_command_metadata(self):
        """Test command metadata and information."""
        command = AgentHandoffCommand(
            target_agent=AgentRole.PLANNING,
            source_agent=AgentRole.WORKSPACE,
            handoff_message="Test message",
            metadata={"test_key": "test_value"}
        )
        
        info = command.get_command_info()
        
        assert info["command_type"] == CommandType.HANDOFF.value
        assert info["status"] == "pending"
        assert info["metadata"]["test_key"] == "test_value"
        assert info["has_error"] is False
        assert "command_id" in info
        assert "created_at" in info


class TestStateModel:
    """Test state model functionality."""
    
    @pytest.fixture
    def state(self):
        """Create a state for testing."""
        return CampaignPlanningState()
    
    def test_state_initialization(self, state):
        """Test state initialization."""
        assert state.current_stage == WorkflowStage.WORKSPACE_ANALYSIS
        assert state.next_agent is None
        assert len(state.active_tasks) == 0
        assert len(state.completed_tasks) == 0
        assert len(state.failed_tasks) == 0
        assert state.workspace_data is not None
        assert state.campaign_plan is not None
        assert state.insights_data is not None
    
    def test_agent_message_handling(self, state):
        """Test agent message addition."""
        from langchain.schema import HumanMessage
        
        message = HumanMessage(content="Test message")
        state.add_agent_message(AgentRole.WORKSPACE, message)
        
        assert len(state.agent_messages[AgentRole.WORKSPACE]) == 1
        assert state.agent_messages[AgentRole.WORKSPACE][0] == message
    
    def test_agent_result_handling(self, state):
        """Test agent result storage."""
        result_data = {"test": "result"}
        state.set_agent_result(AgentRole.PLANNING, result_data)
        
        assert state.agent_results[AgentRole.PLANNING] == result_data
    
    def test_agent_error_handling(self, state):
        """Test agent error tracking."""
        error_message = "Test error occurred"
        state.add_agent_error(AgentRole.INSIGHTS, error_message)
        
        assert len(state.agent_errors[AgentRole.INSIGHTS]) == 1
        assert state.agent_errors[AgentRole.INSIGHTS][0] == error_message
    
    def test_stage_transitions(self, state):
        """Test workflow stage transitions."""
        # Test transition to planning
        state.transition_to_stage(WorkflowStage.PLANNING, AgentRole.PLANNING)
        
        assert state.current_stage == WorkflowStage.PLANNING
        assert state.next_agent == AgentRole.PLANNING
    
    def test_task_management(self, state):
        """Test task addition, completion, and failure."""
        # Add a task
        task = AgentTask(
            id="test-task-1",
            agent_role=AgentRole.WORKSPACE,
            description="Test task"
        )
        
        state.add_task(task)
        assert len(state.active_tasks) == 1
        
        # Complete the task
        state.complete_task("test-task-1", {"result": "success"})
        assert len(state.active_tasks) == 0
        assert len(state.completed_tasks) == 1
        assert state.completed_tasks[0].status == TaskStatus.COMPLETED
        
        # Add and fail another task
        task2 = AgentTask(
            id="test-task-2",
            agent_role=AgentRole.PLANNING,
            description="Test task 2"
        )
        
        state.add_task(task2)
        state.fail_task("test-task-2", "Test error")
        
        assert len(state.failed_tasks) == 1
        assert state.failed_tasks[0].status == TaskStatus.FAILED
        assert state.failed_tasks[0].error == "Test error"
    
    def test_workflow_summary(self, state):
        """Test workflow summary generation."""
        summary = state.get_workflow_summary()
        
        assert summary["current_stage"] == WorkflowStage.WORKSPACE_ANALYSIS.value
        assert summary["next_agent"] is None
        assert summary["active_tasks_count"] == 0
        assert summary["completed_tasks_count"] == 0
        assert summary["failed_tasks_count"] == 0
        assert summary["has_errors"] is False
        assert "workflow_duration" in summary
        assert "last_activity" in summary


# Integration test to verify the complete workflow
class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""
    
    @pytest.mark.asyncio
    async def test_basic_workflow_execution(self):
        """Test basic workflow execution flow."""
        workflow = SupervisorWorkflow()
        initial_state = CampaignPlanningState()
        
        # Set test context
        initial_state.tenant_id = "test-tenant"
        initial_state.user_id = "test-user"
        initial_state.session_id = "test-session"
        
        # Note: This would be a full integration test in a real scenario
        # For now, we'll test individual components
        status = workflow.get_workflow_status()
        assert status["graph_compiled"] is True
        
        # Test command execution
        handoff_command = AgentHandoffCommand(
            target_agent=AgentRole.PLANNING,
            source_agent=AgentRole.WORKSPACE,
            handoff_message="Test workflow handoff"
        )
        
        result = await workflow.execute_command(handoff_command, initial_state)
        
        assert result["handoff_successful"] is True
        assert len(workflow.execution_history) == 1 