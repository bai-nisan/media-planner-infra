"""
Workspace Agent Test Graph for LangSmith Studio

A dedicated graph for testing and debugging the WorkspaceAgent in isolation.
This allows for focused testing of Google Sheets integration, data validation,
and workspace management capabilities.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, Literal
from pathlib import Path
from datetime import datetime

# Add the project root to Python path for absolute imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

# Import our custom state and agent
from app.services.langgraph.workflows.state_models import (
    CampaignPlanningState, 
    WorkflowStage, 
    AgentRole,
    TaskStatus,
    AgentTask
)
from app.services.langgraph.agents.workspace_agent import WorkspaceAgent
from app.services.google.auth import GoogleAuthManager
from app.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkspaceTestNode:
    """Test node for workspace agent operations."""
    
    def __init__(self):
        """Initialize the workspace test node."""
        # Use environment variables or mocked credentials for testing
        self.settings = get_settings()
        
        # For testing, we'll use environment variables
        # In production/real tests, you'd set these in your .env file
        if not os.getenv('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = 'test-key-for-workspace-testing'
            
        self.auth_manager = GoogleAuthManager(self.settings)
        self.workspace_agent = WorkspaceAgent(
            auth_manager=self.auth_manager,
            settings=self.settings
        )
    
    async def workspace_test_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test node that processes workspace operations and returns results.
        This simulates various workspace scenarios for testing.
        """
        try:
            logger.info("🚀 Starting Workspace Agent Test")
            
            # Extract messages from state dictionary
            messages = state.get("messages", [])
            current_stage = state.get("current_stage", "WORKSPACE_ANALYSIS")
            
            # Get the last message to determine what test to run
            last_message = messages[-1] if messages else None
            if last_message:
                # Handle both dictionary and LangChain message formats
                if hasattr(last_message, 'content'):
                    test_instruction = last_message.content
                else:
                    test_instruction = last_message.get("content", "default_test")
            else:
                test_instruction = "default_test"
            
            logger.info(f"📝 Processing test instruction: {test_instruction}")
            
            # Determine test scenario based on user input
            test_scenario = self._parse_test_scenario(test_instruction)
            
            # Convert messages to LangChain format for CampaignPlanningState
            from langchain.schema import HumanMessage, AIMessage
            converted_messages = []
            for msg in messages:
                if hasattr(msg, 'content'):
                    # Already a LangChain message
                    converted_messages.append(msg)
                else:
                    # Convert dictionary to LangChain message
                    role = msg.get("role", "human")
                    content = msg.get("content", "")
                    if role == "human":
                        converted_messages.append(HumanMessage(content=content))
                    else:
                        converted_messages.append(AIMessage(content=content))
            
            # Create a simplified state object for the workspace agent
            simplified_state = CampaignPlanningState(
                messages=converted_messages,
                tenant_id=state.get("tenant_id", "test_tenant"),
                user_id=state.get("user_id", "test_user"),
                session_id=state.get("session_id", "test_session")
            )
            
            # Execute the appropriate test
            result = await self._execute_workspace_test(simplified_state, test_scenario)
            
            # Create response message
            response_content = self._format_test_results(result)
            
            # Use current timestamp instead of relying on state timestamp
            current_timestamp = datetime.now().isoformat()
            
            response_message = {
                "role": "assistant",
                "content": response_content,
                "metadata": {
                    "agent": "workspace_test",
                    "test_scenario": test_scenario,
                    "timestamp": current_timestamp,
                    "success": result.get('success', False)
                }
            }
            
            logger.info(f"✅ Workspace test completed: {test_scenario}")
            
            # Return updated state dictionary
            updated_messages = messages + [response_message]
            
            return {
                "messages": updated_messages,
                "current_stage": "COMPLETE",
                "workspace_data": {
                    "extraction_errors": result.get('errors', []),
                    "google_sheets_data": result.get('google_sheets_data', {}),
                    "validation_results": result.get('validation_results', {})
                },
                "tenant_id": state.get("tenant_id", "test_tenant"),
                "user_id": state.get("user_id", "test_user"),
                "session_id": state.get("session_id", "test_session")
            }
            
        except Exception as e:
            logger.error(f"❌ Workspace test failed: {e}", exc_info=True)
            
            messages = state.get("messages", [])
            
            error_message = {
                "role": "assistant", 
                "content": f"Workspace test failed: {str(e)}",
                "metadata": {
                    "agent": "workspace_test",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "success": False
                }
            }
            
            return {
                "messages": messages + [error_message],
                "current_stage": "ERROR",
                "tenant_id": state.get("tenant_id", "test_tenant"),
                "user_id": state.get("user_id", "test_user"),
                "session_id": state.get("session_id", "test_session")
            }
    
    def _parse_test_scenario(self, instruction: str) -> str:
        """Parse user instruction to determine test scenario."""
        instruction_lower = instruction.lower()
        
        if "google" in instruction_lower and "sheet" in instruction_lower:
            return "google_sheets_extraction"
        elif "validate" in instruction_lower or "validation" in instruction_lower:
            return "data_validation"
        elif "discover" in instruction_lower or "files" in instruction_lower:
            return "file_discovery"
        elif "workspace" in instruction_lower and "analyze" in instruction_lower:
            return "workspace_analysis"
        elif "transform" in instruction_lower or "format" in instruction_lower:
            return "data_transformation"
        else:
            return "full_workflow_test"
    
    async def _execute_workspace_test(self, state: CampaignPlanningState, scenario: str) -> Dict[str, Any]:
        """Execute the specific test scenario."""
        
        if scenario == "google_sheets_extraction":
            return await self._test_google_sheets_extraction(state)
        elif scenario == "data_validation":
            return await self._test_data_validation(state)
        elif scenario == "file_discovery":
            return await self._test_file_discovery(state)
        elif scenario == "workspace_analysis":
            return await self._test_workspace_analysis(state)
        elif scenario == "data_transformation":
            return await self._test_data_transformation(state)
        else:
            return await self._test_full_workflow(state)
    
    async def _test_google_sheets_extraction(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Test Google Sheets data extraction."""
        logger.info("🔍 Testing Google Sheets extraction...")
        
        # Create a test task for Google Sheets extraction
        task = {
            "type": "extract_google_sheets",
            "data": {
                "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",  # Sample public sheet
                "range": "Class Data!A2:E"
            }
        }
        
        try:
            # Process task through workspace agent
            command_result = await self.workspace_agent.process_task(state, task)
            
            return {
                "success": True,
                "scenario": "google_sheets_extraction",
                "google_sheets_data": {
                    "extracted": True,
                    "command_result": str(command_result),
                    "next_agent": command_result.goto if hasattr(command_result, 'goto') else None
                },
                "message": "Google Sheets extraction test completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "scenario": "google_sheets_extraction", 
                "errors": [str(e)],
                "message": f"Google Sheets extraction test failed: {str(e)}"
            }
    
    async def _test_data_validation(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Test data validation capabilities."""
        logger.info("🔍 Testing data validation...")
        
        # Create test data for validation
        test_data = {
            "campaigns": [
                {"name": "Campaign 1", "budget": 1000, "status": "active"},
                {"name": "Campaign 2", "budget": 500, "status": "paused"}
            ],
            "keywords": ["marketing", "advertising", "digital"]
        }
        
        task = {
            "type": "validate_data",
            "data": {
                "data_to_validate": test_data,
                "validation_rules": ["budget_positive", "status_valid", "name_required"]
            }
        }
        
        try:
            command_result = await self.workspace_agent.process_task(state, task)
            
            return {
                "success": True,
                "scenario": "data_validation",
                "validation_results": {
                    "validated": True,
                    "command_result": str(command_result),
                    "test_data": test_data
                },
                "message": "Data validation test completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "scenario": "data_validation",
                "errors": [str(e)],
                "message": f"Data validation test failed: {str(e)}"
            }
    
    async def _test_file_discovery(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Test file discovery functionality."""
        logger.info("🔍 Testing file discovery...")
        
        task = {
            "type": "discover_files",
            "data": {
                "search_keywords": ["campaign", "budget", "marketing"],
                "file_types": ["spreadsheet", "document"]
            }
        }
        
        try:
            command_result = await self.workspace_agent.process_task(state, task)
            
            return {
                "success": True,
                "scenario": "file_discovery",
                "discovery_results": {
                    "discovered": True,
                    "command_result": str(command_result)
                },
                "message": "File discovery test completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "scenario": "file_discovery",
                "errors": [str(e)],
                "message": f"File discovery test failed: {str(e)}"
            }
    
    async def _test_workspace_analysis(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Test workspace analysis functionality."""
        logger.info("🔍 Testing workspace analysis...")
        
        task = {
            "type": "analyze_workspace", 
            "data": {
                "workspace_id": "test_workspace",
                "analysis_depth": "comprehensive"
            }
        }
        
        try:
            command_result = await self.workspace_agent.process_task(state, task)
            
            return {
                "success": True,
                "scenario": "workspace_analysis",
                "analysis_results": {
                    "analyzed": True,
                    "command_result": str(command_result)
                },
                "message": "Workspace analysis test completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "scenario": "workspace_analysis",
                "errors": [str(e)],
                "message": f"Workspace analysis test failed: {str(e)}"
            }
    
    async def _test_data_transformation(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Test data transformation functionality."""
        logger.info("🔍 Testing data transformation...")
        
        raw_data = {
            "raw_campaigns": [
                {"Campaign Name": "Test Campaign", "Budget $": "1000", "Status": "Active"},
                {"Campaign Name": "Another Campaign", "Budget $": "500", "Status": "Paused"}
            ]
        }
        
        task = {
            "type": "transform_data",
            "data": {
                "raw_data": raw_data,
                "target_format": "standardized_campaign_format"
            }
        }
        
        try:
            command_result = await self.workspace_agent.process_task(state, task)
            
            return {
                "success": True,
                "scenario": "data_transformation",
                "transformation_results": {
                    "transformed": True,
                    "command_result": str(command_result),
                    "input_data": raw_data
                },
                "message": "Data transformation test completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "scenario": "data_transformation",
                "errors": [str(e)],
                "message": f"Data transformation test failed: {str(e)}"
            }
    
    async def _test_full_workflow(self, state: CampaignPlanningState) -> Dict[str, Any]:
        """Run a comprehensive test of all workspace capabilities."""
        logger.info("🔍 Running full workspace workflow test...")
        
        results = {}
        all_success = True
        
        # Test each capability in sequence
        test_scenarios = [
            "google_sheets_extraction",
            "data_validation", 
            "file_discovery",
            "workspace_analysis",
            "data_transformation"
        ]
        
        for scenario in test_scenarios:
            try:
                result = await self._execute_workspace_test(state, scenario)
                results[scenario] = result
                if not result.get('success', False):
                    all_success = False
            except Exception as e:
                results[scenario] = {
                    "success": False,
                    "error": str(e)
                }
                all_success = False
        
        return {
            "success": all_success,
            "scenario": "full_workflow_test",
            "detailed_results": results,
            "message": f"Full workflow test completed - {'All tests passed' if all_success else 'Some tests failed'}"
        }
    
    def _format_test_results(self, result: Dict[str, Any]) -> str:
        """Format test results for display."""
        scenario = result.get('scenario', 'unknown')
        success = result.get('success', False)
        message = result.get('message', 'No message provided')
        
        status_emoji = "✅" if success else "❌"
        
        formatted = f"{status_emoji} **Workspace Agent Test: {scenario.title()}**\n\n"
        formatted += f"**Status:** {'PASSED' if success else 'FAILED'}\n"
        formatted += f"**Message:** {message}\n\n"
        
        if 'detailed_results' in result:
            formatted += "**Detailed Results:**\n"
            for test_name, test_result in result['detailed_results'].items():
                test_status = "✅" if test_result.get('success', False) else "❌"
                formatted += f"- {test_status} {test_name}: {test_result.get('message', 'No details')}\n"
        
        if 'errors' in result and result['errors']:
            formatted += "\n**Errors:**\n"
            for error in result['errors']:
                formatted += f"- {error}\n"
        
        return formatted


def create_workspace_test_graph():
    """Create and compile the workspace test graph."""
    try:
        logger.info("🔧 Creating workspace test graph...")
        
        # Initialize the test node
        test_node = WorkspaceTestNode()
        
        # Create the state graph
        builder = StateGraph(CampaignPlanningState)
        
        # Add our test node
        builder.add_node("workspace_test", test_node.workspace_test_node)
        
        # Simple flow: START -> workspace_test -> END
        builder.add_edge(START, "workspace_test")
        builder.add_edge("workspace_test", END)
        
        # Compile the graph (LangGraph API handles persistence automatically)
        compiled_graph = builder.compile()
        
        logger.info("✅ Workspace test graph compiled successfully!")
        return compiled_graph
        
    except Exception as e:
        logger.error(f"❌ Failed to create workspace test graph: {e}")
        raise


# Create the graph instance for LangGraph server
graph = create_workspace_test_graph()

# Export for LangGraph CLI
__all__ = ["graph"]


# For debugging and development
if __name__ == "__main__":
    import asyncio
    from langchain.schema import HumanMessage
    
    async def test_locally():
        """Test the graph locally."""
        print("🧪 Testing workspace graph locally...")
        
        try:
            # Create initial state as dictionary (matching LangGraph format)
            initial_state = {
                "messages": [
                    {"role": "human", "content": "Test Google Sheets extraction functionality"}
                ],
                "tenant_id": "test_tenant",
                "user_id": "test_user",
                "session_id": "test_session"
            }
            
            # Run the graph
            result = await graph.ainvoke(initial_state)
            
            print("✅ Local test completed successfully!")
            
            # Handle both dictionary and LangChain message formats
            final_message = result['messages'][-1]
            if hasattr(final_message, 'content'):
                print(f"Final message: {final_message.content}")
            else:
                print(f"Final message: {final_message['content']}")
            
        except Exception as e:
            print(f"❌ Local test failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Run local test
    asyncio.run(test_locally()) 