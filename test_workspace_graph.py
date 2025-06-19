#!/usr/bin/env python3
"""
Test script for the workspace agent graph.

Run this script to test the workspace agent functionality locally
before using LangSmith Studio.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up test environment
os.environ["OPENAI_API_KEY"] = "test-key-for-workspace-testing"

from workspace_test_graph import graph


async def test_workspace_scenarios():
    """Test different workspace scenarios."""

    test_scenarios = [
        {
            "name": "Google Sheets Extraction",
            "message": "Test Google Sheets extraction functionality",
        },
        {"name": "Data Validation", "message": "Test data validation capabilities"},
        {"name": "File Discovery", "message": "Test file discovery functionality"},
        {
            "name": "Workspace Analysis",
            "message": "Test workspace analysis capabilities",
        },
        {
            "name": "Full Workflow",
            "message": "Run a comprehensive test of all workspace capabilities",
        },
    ]

    print("🧪 Testing Workspace Agent Graph")
    print("=" * 50)

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📋 Test {i}/{len(test_scenarios)}: {scenario['name']}")
        print("-" * 30)

        try:
            # Create initial state as dictionary
            initial_state = {
                "messages": [{"role": "human", "content": scenario["message"]}],
                "tenant_id": "test_tenant",
                "user_id": "test_user",
                "session_id": f"test_session_{i}",
            }

            # Run the graph
            result = await graph.ainvoke(initial_state)

            # Get the final message
            final_message = result["messages"][-1]

            # Handle both dictionary and LangChain message formats
            if hasattr(final_message, "metadata"):
                success = (
                    final_message.metadata.get("success", False)
                    if final_message.metadata
                    else False
                )
                content = (
                    final_message.content
                    if hasattr(final_message, "content")
                    else "No content"
                )
            else:
                success = final_message.get("metadata", {}).get("success", False)
                content = final_message.get("content", "No content")

            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"Status: {status}")

            print(f"Response: {content[:200]}...")

        except Exception as e:
            print(f"❌ FAILED: {str(e)}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 50)
    print("🏁 Workspace Agent Testing Complete!")


if __name__ == "__main__":
    asyncio.run(test_workspace_scenarios())
