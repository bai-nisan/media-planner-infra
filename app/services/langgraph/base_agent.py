"""
Base Agent class for LangGraph Multi-Agent System
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.chat_models import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.types import Command

from .config import AgentConfig, AgentType


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system."""
    
    def __init__(self, config: AgentConfig, supabase_client=None):
        self.config = config
        self.supabase_client = supabase_client
        self.agent_id = f"{config.type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model_name=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        logger.info(f"Initialized {config.name} with ID: {self.agent_id}")
    
    @abstractmethod
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize agent-specific tools."""
        pass
    
    @abstractmethod
    async def process_task(self, state: MessagesState, task: Dict[str, Any]) -> Command:
        """Process a task and return a command for routing."""
        pass
    
    async def _call_llm(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the LLM with messages."""
        try:
            # Add system prompt if not already present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=self.config.system_prompt)] + messages
            
            response = await self.llm.ainvoke(messages)
            return response
        except Exception as e:
            logger.error(f"Error calling LLM for {self.config.name}: {e}")
            raise
    
    async def _save_state(self, state_data: Dict[str, Any]) -> None:
        """Save agent state to Supabase."""
        if not self.supabase_client:
            logger.warning("No Supabase client available for state persistence")
            return
        
        try:
            state_record = {
                "agent_id": self.agent_id,
                "agent_type": self.config.type.value,
                "state_data": state_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await self.supabase_client.table("agent_states").upsert(state_record).execute()
            logger.debug(f"Saved state for {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error saving state for {self.config.name}: {e}")
    
    async def _load_state(self) -> Optional[Dict[str, Any]]:
        """Load agent state from Supabase."""
        if not self.supabase_client:
            return None
        
        try:
            result = await self.supabase_client.table("agent_states")\
                .select("state_data")\
                .eq("agent_id", self.agent_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                return result.data[0]["state_data"]
            return None
            
        except Exception as e:
            logger.error(f"Error loading state for {self.config.name}: {e}")
            return None
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Any]:
        """Get a tool by name."""
        return self.tools.get(tool_name)
    
    def list_available_tools(self) -> List[str]:
        """List all available tools for this agent."""
        return list(self.tools.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for the agent."""
        try:
            # Test LLM connectivity
            test_message = HumanMessage(content="Health check")
            await self._call_llm([test_message])
            
            return {
                "agent_id": self.agent_id,
                "agent_type": self.config.type.value,
                "status": "healthy",
                "tools_count": len(self.tools),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "agent_type": self.config.type.value,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            } 