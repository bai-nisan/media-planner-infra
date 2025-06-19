"""
LangGraph Server Entry Point

This module provides the compiled graph for LangGraph Server to serve
the multi-agent system for media planning.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add the project root to Python path for absolute imports
project_root = Path(__file__).parents[3]  # Go up 3 levels to reach media-planner-infra
sys.path.insert(0, str(project_root))

from langgraph.checkpoint.memory import MemorySaver

from app.services.langgraph.workflows.state_models import CampaignPlanningState

# Use absolute imports that work when module is executed directly
from app.services.langgraph.workflows.supervisor import SupervisorWorkflow

# Configure logging
logger = logging.getLogger(__name__)


# Initialize checkpointer - using MemorySaver for development
def get_checkpointer():
    """Get the appropriate checkpointer based on configuration."""
    # For now, use MemorySaver for development
    # TODO: Add PostgreSQL support later in the setup process
    return MemorySaver()


# Initialize the workflow
def create_graph():
    """Create and compile the media planning graph."""
    try:
        logger.info("Initializing SupervisorWorkflow...")
        workflow = SupervisorWorkflow()

        logger.info("Getting compiled graph from workflow...")
        # The SupervisorWorkflow automatically builds and compiles the graph in __init__
        compiled_graph = workflow.compiled_graph

        if compiled_graph is None:
            raise ValueError("Failed to compile workflow graph")

        logger.info("✅ Media planning graph compiled successfully!")
        return compiled_graph

    except Exception as e:
        logger.error(f"❌ Failed to create graph: {e}")
        raise


# Create the graph instance for LangGraph server
graph = create_graph()

# Export for LangGraph CLI
__all__ = ["graph"]


def create_graph(config: Dict[str, Any] = None) -> Any:
    """
    Factory function to create a new graph instance.

    This function can be used when dynamic graph configuration is needed
    based on runtime parameters.

    Args:
        config: Configuration dictionary for the graph

    Returns:
        Compiled graph instance
    """
    # Create new workflow instance with config
    workflow_instance = SupervisorWorkflow(config)

    # Get checkpointer
    checkpointer_instance = get_checkpointer()

    # Compile and return the graph
    return workflow_instance.graph.compile(checkpointer=checkpointer_instance)


# For debugging and development
if __name__ == "__main__":
    # Test the graph creation
    print("Testing graph compilation...")

    try:
        test_config = {"max_iterations": 10, "timeout_seconds": 300, "debug": True}

        test_graph = create_graph(test_config)
        print("✅ Graph compiled successfully!")

        # Test basic invocation
        test_state = CampaignPlanningState()
        print("Testing basic graph invocation...")

        # Note: This would need actual agent implementations to work
        # result = await test_graph.ainvoke(test_state)
        # print("✅ Graph invocation successful!")

    except Exception as e:
        print(f"❌ Graph compilation failed: {e}")
        import traceback

        traceback.print_exc()
