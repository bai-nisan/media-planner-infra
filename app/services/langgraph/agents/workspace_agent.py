"""
Workspace Agent for Media Planning Platform

Handles Google Sheet parsing, data extraction, and workspace management.
"""

import logging
from typing import Dict, Any, List, Literal
from datetime import datetime

from langchain.schema import HumanMessage
from langgraph.graph import MessagesState
from langgraph.types import Command

from ..base_agent import BaseAgent
from ..tools.workspace_tools import (
    GoogleSheetsReader,
    FileParser,
    DataValidator,
    WorkspaceManager
)


logger = logging.getLogger(__name__)


class WorkspaceAgent(BaseAgent):
    """Agent responsible for workspace operations and data extraction."""
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize workspace-specific tools."""
        return {
            "google_sheets_reader": GoogleSheetsReader(),
            "file_parser": FileParser(),
            "data_validator": DataValidator(),
            "workspace_manager": WorkspaceManager()
        }
    
    async def process_task(
        self, 
        state: MessagesState, 
        task: Dict[str, Any]
    ) -> Command[Literal["supervisor", "planning", "insights", "__end__"]]:
        """Process workspace-related tasks."""
        try:
            task_type = task.get("type", "")
            task_data = task.get("data", {})
            
            logger.info(f"Processing workspace task: {task_type}")
            
            result = None
            next_agent = "supervisor"
            
            if task_type == "extract_google_sheets":
                result = await self._extract_google_sheets(task_data)
                next_agent = "planning"  # Send extracted data to planning agent
                
            elif task_type == "parse_campaign_file":
                result = await self._parse_campaign_file(task_data)
                next_agent = "planning"
                
            elif task_type == "validate_data":
                result = await self._validate_data(task_data)
                next_agent = "supervisor"  # Return validation results to supervisor
                
            elif task_type == "manage_workspace":
                result = await self._manage_workspace(task_data)
                next_agent = "supervisor"
                
            else:
                raise ValueError(f"Unknown task type: {task_type}")
            
            # Update state with results
            response_message = {
                "role": "assistant",
                "content": f"Workspace task completed: {task_type}",
                "metadata": {
                    "agent": "workspace",
                    "task_type": task_type,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Save state
            await self._save_state({
                "last_task": task_type,
                "last_result": result,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return Command(
                goto=next_agent,
                update={"messages": state["messages"] + [response_message]}
            )
            
        except Exception as e:
            logger.error(f"Error processing workspace task: {e}")
            
            error_message = {
                "role": "assistant",
                "content": f"Workspace task failed: {str(e)}",
                "metadata": {
                    "agent": "workspace",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            return Command(
                goto="supervisor",
                update={"messages": state["messages"] + [error_message]}
            )
    
    async def _extract_google_sheets(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from Google Sheets."""
        sheets_reader = self.tools["google_sheets_reader"]
        
        spreadsheet_id = task_data.get("spreadsheet_id")
        sheet_range = task_data.get("range", "A1:Z1000")
        
        if not spreadsheet_id:
            raise ValueError("Spreadsheet ID is required")
        
        # Extract data using Google Sheets API
        extracted_data = await sheets_reader.extract_data(spreadsheet_id, sheet_range)
        
        # Validate extracted data
        validator = self.tools["data_validator"]
        validation_result = await validator.validate_sheet_data(extracted_data)
        
        return {
            "extracted_data": extracted_data,
            "validation": validation_result,
            "metadata": {
                "spreadsheet_id": spreadsheet_id,
                "range": sheet_range,
                "row_count": len(extracted_data.get("rows", [])),
                "extraction_time": datetime.utcnow().isoformat()
            }
        }
    
    async def _parse_campaign_file(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse campaign files."""
        file_parser = self.tools["file_parser"]
        
        file_path = task_data.get("file_path")
        file_type = task_data.get("file_type", "auto")
        
        if not file_path:
            raise ValueError("File path is required")
        
        # Parse the file
        parsed_data = await file_parser.parse_file(file_path, file_type)
        
        # Validate parsed data
        validator = self.tools["data_validator"]
        validation_result = await validator.validate_campaign_data(parsed_data)
        
        return {
            "parsed_data": parsed_data,
            "validation": validation_result,
            "metadata": {
                "file_path": file_path,
                "file_type": file_type,
                "parse_time": datetime.utcnow().isoformat()
            }
        }
    
    async def _validate_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data integrity and format."""
        validator = self.tools["data_validator"]
        
        data_to_validate = task_data.get("data")
        validation_type = task_data.get("validation_type", "general")
        
        if not data_to_validate:
            raise ValueError("Data to validate is required")
        
        # Perform validation
        validation_result = await validator.validate_data(data_to_validate, validation_type)
        
        return {
            "validation_result": validation_result,
            "is_valid": validation_result.get("is_valid", False),
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", []),
            "metadata": {
                "validation_type": validation_type,
                "validation_time": datetime.utcnow().isoformat()
            }
        }
    
    async def _manage_workspace(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage workspace operations."""
        workspace_manager = self.tools["workspace_manager"]
        
        operation = task_data.get("operation")
        operation_data = task_data.get("operation_data", {})
        
        if not operation:
            raise ValueError("Workspace operation is required")
        
        # Execute workspace operation
        result = await workspace_manager.execute_operation(operation, operation_data)
        
        return {
            "operation": operation,
            "result": result,
            "metadata": {
                "operation_time": datetime.utcnow().isoformat()
            }
        } 