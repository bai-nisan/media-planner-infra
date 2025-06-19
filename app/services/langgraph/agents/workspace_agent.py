"""
Enhanced WorkspaceAgent with Auth Service Integration

Enhanced agent with real Google Sheets integration, robust data validation,
and seamless credential management through the auth service.
"""

import logging
from typing import Dict, Any, List, Literal, Optional
from datetime import datetime

from langchain.schema import HumanMessage
from langgraph.graph import MessagesState
from langgraph.types import Command

from ..base_agent import BaseAgent
from ..config import AgentConfig, AgentType
from ..tools.workspace_tools import (
    GoogleSheetsReader,
    FileParser,
    DataValidator,
    WorkspaceManager
)
from ..workflows.state_models import WorkspaceData, AgentTask, TaskStatus
from app.services.google.auth_enhanced import (
    AuthServiceIntegratedManager,
    AgentAuthManagerFactory,
    ManagedGoogleAuth
)
from app.core.config import get_settings


logger = logging.getLogger(__name__)


class WorkspaceAgent(BaseAgent):
    """Enhanced agent for workspace operations with auth service integration."""
    
    def __init__(
        self, 
        auth_manager: Optional[AuthServiceIntegratedManager] = None, 
        settings=None, 
        config: Optional[AgentConfig] = None,
        tenant_id: Optional[str] = None,
        auth_service_url: Optional[str] = None
    ):
        """
        Initialize the WorkspaceAgent with enhanced auth service integration.
        
        Args:
            auth_manager: Enhanced auth manager with service integration
            settings: Application settings
            config: Agent configuration
            tenant_id: Tenant ID for multi-tenant environments
            auth_service_url: Custom auth service URL
        """
        # Create default config if not provided
        if config is None:
            config = AgentConfig(
                name="WorkspaceAgent",
                type=AgentType.WORKSPACE,
                description="Handles Google Sheet parsing, data extraction, and workspace management with auth service integration",
                model_name="gpt-4-turbo-preview",
                temperature=0.3,
                tools=[
                    "google_sheets_reader",
                    "file_parser", 
                    "data_validator",
                    "workspace_manager"
                ],
                system_prompt="""You are the Workspace Agent with enhanced auth service integration.
                
Your primary responsibilities:
- Parse and extract data from Google Sheets using secure credential management
- Validate data integrity and format with quality scoring
- Manage file operations and workspace structure
- Handle data transformations for downstream agents
- Ensure secure authentication across all Google API operations

You have access to centralized credential management through the auth service,
providing seamless authentication across multi-tenant environments."""
            )
        
        # Get settings first
        if settings is None:
            settings = get_settings()
        self.settings = settings
        self.tenant_id = tenant_id
        
        # Create enhanced auth manager with service integration
        if auth_manager is None:
            auth_manager = AgentAuthManagerFactory.create_workspace_agent_auth(
                settings=settings,
                tenant_id=tenant_id,
                auth_service_url=auth_service_url
            )
        self.auth_manager = auth_manager
        
        # Initialize tools with enhanced auth manager
        # This is necessary because BaseAgent.__init__ calls _initialize_tools()
        self.sheets_reader = GoogleSheetsReader(auth_manager, settings)
        self.file_parser = FileParser(auth_manager, settings) 
        self.data_validator = DataValidator()
        self.workspace_manager = WorkspaceManager(auth_manager, settings)
        
        # Now call super().__init__ which will call _initialize_tools()
        super().__init__(config)
        
        logger.info(f"Initialized WorkspaceAgent with auth service integration for tenant: {tenant_id or 'default'}")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize workspace-specific tools with enhanced auth integration."""
        return {
            "google_sheets_reader": self.sheets_reader,
            "file_parser": self.file_parser,
            "data_validator": self.data_validator,
            "workspace_manager": self.workspace_manager
        }
    
    async def process_task(
        self, 
        state: MessagesState, 
        task: Dict[str, Any]
    ) -> Command[Literal["supervisor_agent", "planning_agent", "insights_agent", "__end__"]]:
        """Process workspace-related tasks with enhanced auth service integration."""
        try:
            task_type = task.get("type", "")
            task_data = task.get("data", {})
            
            logger.info(f"WorkspaceAgent processing task: {task_type} with auth service integration")
            
            # Check credential status before processing
            await self._ensure_valid_credentials()
            
            # Route to appropriate handler
            if task_type == "extract_google_sheets":
                result = await self._handle_extract_google_sheets(task_data)
                next_agent = "planning_agent"  # Send extracted data to planning
                
            elif task_type == "validate_data":
                result = await self._handle_validate_data(task_data)
                next_agent = "supervisor_agent"  # Return validation to supervisor
                
            elif task_type == "transform_data":
                result = await self._handle_transform_data(task_data)
                next_agent = "supervisor_agent"
                
            elif task_type == "analyze_workspace":
                result = await self._handle_analyze_workspace(task_data)
                next_agent = "supervisor_agent"
                
            elif task_type == "discover_files":
                result = await self._handle_discover_files(task_data)
                next_agent = "supervisor_agent"
                
            elif task_type == "check_auth_status":
                result = await self._handle_check_auth_status(task_data)
                next_agent = "supervisor_agent"
                
            else:
                raise ValueError(f"Unknown workspace task type: {task_type}")
            
            # Update workspace data in state
            if hasattr(state, 'workspace_data') and isinstance(state.workspace_data, WorkspaceData):
                await self._update_workspace_data(state.workspace_data, task_type, result)
            
            # Create response message with auth info
            response_message = {
                "role": "assistant",
                "content": f"WorkspaceAgent completed: {task_type} (auth service integrated)",
                "metadata": {
                    "agent": "workspace",
                    "task_type": task_type,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "tenant_id": self.tenant_id,
                    "auth_service_integrated": True
                }
            }
            
            # Save agent state with auth info
            await self._save_state({
                "last_task": task_type,
                "last_result": result,
                "timestamp": datetime.utcnow().isoformat(),
                "tenant_id": self.tenant_id,
                "auth_service_integrated": True
            })
            
            logger.info(f"WorkspaceAgent successfully completed {task_type}, routing to {next_agent}")
            
            return Command(
                goto=next_agent,
                update={"messages": state["messages"] + [response_message]}
            )
            
        except Exception as e:
            logger.error(f"WorkspaceAgent error processing task: {e}", exc_info=True)
            
            # Update workspace data with error
            if hasattr(state, 'workspace_data') and isinstance(state.workspace_data, WorkspaceData):
                state.workspace_data.extraction_errors.append(str(e))
            
            error_message = {
                "role": "assistant",
                "content": f"WorkspaceAgent task failed: {str(e)}",
                "metadata": {
                    "agent": "workspace",
                    "task_type": task.get("type", "unknown"),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False,
                    "tenant_id": self.tenant_id
                }
            }
            
            return Command(
                goto="supervisor_agent",
                update={"messages": state["messages"] + [error_message]}
            )
    
    async def _ensure_valid_credentials(self) -> bool:
        """
        Ensure we have valid credentials before processing tasks.
        
        Uses the auth service integration to check and refresh credentials.
        
        Returns:
            True if credentials are valid, raises exception otherwise
        """
        try:
            async with ManagedGoogleAuth(self.auth_manager, auto_refresh=True) as credentials:
                if credentials is None:
                    raise ValueError("No valid Google credentials available from auth service")
                
                logger.debug("Valid credentials confirmed from auth service")
                return True
                
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            # Get detailed status for debugging
            status = await self.auth_manager.get_credential_status()
            logger.error(f"Credential status: {status}")
            raise ValueError(f"Authentication required: {str(e)}")
    
    async def _handle_extract_google_sheets(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Sheets extraction with auth service integration."""
        logger.info("Handling extract_google_sheets task with auth service")
        
        spreadsheet_id = task_data.get("spreadsheet_id")
        sheet_range = task_data.get("range", "A1:Z1000")
        
        if not spreadsheet_id:
            raise ValueError("Spreadsheet ID is required for extraction")
        
        # Extract data using auth service managed credentials
        async with ManagedGoogleAuth(self.auth_manager) as credentials:
            if not credentials:
                raise ValueError("Failed to obtain valid credentials from auth service")
            
            extracted_data = await self.sheets_reader.extract_data(spreadsheet_id, sheet_range)
        
        # Enhanced validation with data quality scoring
        validation_result = await self.data_validator.validate_extracted_sheet_data(extracted_data)
        
        # Calculate overall data quality score
        data_quality_score = validation_result.get("data_quality_score", 0.0)
        campaigns_found = len(extracted_data.get("parsed_campaigns", []))
        
        result = {
            "extracted_data": extracted_data,
            "validation": validation_result,
            "data_quality_score": data_quality_score,
            "campaigns_count": campaigns_found,
            "metadata": {
                "spreadsheet_id": spreadsheet_id,
                "range": sheet_range,
                "extraction_time": datetime.utcnow().isoformat(),
                "row_count": len(extracted_data.get("rows", [])),
                "column_count": len(extracted_data.get("headers", [])),
                "status": "success" if data_quality_score > 0.5 else "low_quality",
                "auth_source": "auth_service",
                "tenant_id": self.tenant_id
            }
        }
        
        logger.info(f"Extracted {campaigns_found} campaigns with quality score {data_quality_score}")
        return result
    
    async def _handle_check_auth_status(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle authentication status checking.
        
        Provides comprehensive status of credential sources and validity.
        """
        try:
            # Get comprehensive credential status
            status = await self.auth_manager.get_credential_status()
            
            # Test actual credential retrieval
            async with ManagedGoogleAuth(self.auth_manager) as credentials:
                can_authenticate = credentials is not None
            
            result = {
                "auth_status": status,
                "can_authenticate": can_authenticate,
                "tenant_id": self.tenant_id,
                "service_id": self.auth_manager.service_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Auth status check completed for tenant {self.tenant_id}: {can_authenticate}")
            return result
            
        except Exception as e:
            logger.error(f"Auth status check failed: {e}")
            return {
                "auth_status": {"error": str(e)},
                "can_authenticate": False,
                "tenant_id": self.tenant_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _handle_validate_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data validation with enhanced auth integration."""
        logger.info("Handling validate_data task")
        
        data_to_validate = task_data.get("data", {})
        validation_type = task_data.get("validation_type", "campaign_data")
        
        if validation_type == "campaign_data":
            validation_result = await self.data_validator.validate_campaign_data(data_to_validate)
        elif validation_type == "extracted_sheet_data":
            validation_result = await self.data_validator.validate_extracted_sheet_data(data_to_validate)
        else:
            # General data validation
            validation_result = await self.data_validator.validate_data_structure(data_to_validate)
        
        result = {
            "validation": validation_result,
            "data_valid": validation_result.get("is_valid", False),
            "quality_score": validation_result.get("data_quality_score", 0.0),
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", []),
            "metadata": {
                "validation_type": validation_type,
                "timestamp": datetime.utcnow().isoformat(),
                "tenant_id": self.tenant_id
            }
        }
        
        logger.info(f"Data validation completed with quality score: {result['quality_score']}")
        return result
    
    async def _handle_transform_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data transformation for standardized format."""
        logger.info("Handling transform_data task")
        
        raw_data = task_data.get("data")
        transformation_type = task_data.get("transformation_type", "campaign_standardization")
        
        if not raw_data:
            raise ValueError("Data to transform is required")
        
        # Apply transformations based on type
        if transformation_type == "campaign_standardization":
            transformed_data = await self._standardize_campaign_data(raw_data)
        elif transformation_type == "budget_normalization":
            transformed_data = await self._normalize_budget_data(raw_data)
        else:
            transformed_data = raw_data  # No transformation applied
        
        result = {
            "transformed_data": transformed_data,
            "transformation_type": transformation_type,
            "transformation_applied": transformation_type in ["campaign_standardization", "budget_normalization"],
            "metadata": {
                "original_format": type(raw_data).__name__,
                "transformation_time": datetime.utcnow().isoformat(),
                "records_processed": len(transformed_data) if isinstance(transformed_data, list) else 1
            }
        }
        
        logger.info(f"Data transformation completed: {transformation_type}")
        return result
    
    async def _handle_analyze_workspace(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle comprehensive workspace analysis."""
        logger.info("Handling analyze_workspace task")
        
        # Discover campaign files
        discovery_result = await self.workspace_manager.discover_campaign_files()
        
        # Validate discovered workspace
        validation_result = await self.workspace_manager.validate_workspace(
            discovery_result.get("discovered_files", [])
        )
        
        # Analyze workspace quality and completeness
        analysis = {
            "workspace_quality": self._calculate_workspace_quality(discovery_result, validation_result),
            "file_count": len(discovery_result.get("discovered_files", [])),
            "spreadsheet_count": len([f for f in discovery_result.get("discovered_files", []) 
                                    if f.get("file_type") == "google_sheets"]),
            "validation_score": validation_result.get("overall_score", 0.0),
            "recommendations": self._generate_workspace_recommendations(discovery_result, validation_result)
        }
        
        result = {
            "discovery": discovery_result,
            "validation": validation_result,
            "analysis": analysis,
            "metadata": {
                "analysis_time": datetime.utcnow().isoformat(),
                "workspace_health": "healthy" if analysis["workspace_quality"] > 0.7 else "needs_attention"
            }
        }
        
        logger.info(f"Workspace analysis completed: quality={analysis['workspace_quality']:.2f}")
        return result
    
    async def _handle_discover_files(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file discovery in workspace."""
        logger.info("Handling discover_files task")
        
        file_types = task_data.get("file_types", ["google_sheets", "google_docs"])
        keywords = task_data.get("keywords", ["campaign", "media", "ads", "budget"])
        
        # Discover files using workspace manager
        discovery_result = await self.workspace_manager.discover_campaign_files()
        
        # Filter by requested file types if specified
        discovered_files = discovery_result.get("discovered_files", [])
        if file_types and file_types != ["all"]:
            discovered_files = [f for f in discovered_files if f.get("file_type") in file_types]
        
        result = {
            "discovered_files": discovered_files,
            "file_count": len(discovered_files),
            "file_types_found": list(set(f.get("file_type") for f in discovered_files)),
            "discovery_summary": discovery_result.get("discovery_metadata", {}),
            "metadata": {
                "discovery_time": datetime.utcnow().isoformat(),
                "search_criteria": {
                    "file_types": file_types,
                    "keywords": keywords
                }
            }
        }
        
        logger.info(f"File discovery completed: {len(discovered_files)} files found")
        return result
    
    async def _update_workspace_data(self, workspace_data: WorkspaceData, task_type: str, result: Dict[str, Any]):
        """Update WorkspaceData state with task results."""
        try:
            if task_type == "extract_google_sheets":
                workspace_data.google_sheets_data = result.get("extracted_data")
                workspace_data.campaign_data = {
                    "campaigns": result.get("extracted_data", {}).get("parsed_campaigns", []),
                    "data_quality_score": result.get("data_quality_score", 0.0)
                }
                workspace_data.validation_results = result.get("validation")
                
            elif task_type == "validate_data":
                workspace_data.validation_results = result.get("validation_result")
                
            elif task_type == "analyze_workspace":
                workspace_data.drive_files = result.get("discovery", {}).get("discovered_files", [])
                
            elif task_type == "discover_files":
                workspace_data.drive_files = result.get("discovered_files", [])
            
            logger.debug(f"Updated workspace data for task: {task_type}")
            
        except Exception as e:
            logger.error(f"Error updating workspace data: {e}")
            workspace_data.extraction_errors.append(f"State update error: {str(e)}")
    
    async def _standardize_campaign_data(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Standardize campaign data format."""
        if not isinstance(raw_data, dict):
            return []
        
        campaigns = raw_data.get("parsed_campaigns", [])
        standardized = []
        
        for campaign in campaigns:
            standardized_campaign = {
                "id": f"campaign_{len(standardized) + 1}",
                "name": campaign.get("campaign_name", "Unknown Campaign"),
                "budget": float(campaign.get("budget", 0)) if campaign.get("budget") else 0.0,
                "start_date": campaign.get("start_date"),
                "end_date": campaign.get("end_date"),
                "platform": campaign.get("platform", "unknown"),
                "targeting": campaign.get("targeting", {}),
                "metrics": campaign.get("metrics", {}),
                "status": "active",
                "created_at": datetime.utcnow().isoformat()
            }
            standardized.append(standardized_campaign)
        
        return standardized
    
    async def _normalize_budget_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize budget data to standard format."""
        if not isinstance(raw_data, dict):
            return raw_data
        
        # Extract budget information and normalize
        campaigns = raw_data.get("parsed_campaigns", [])
        total_budget = 0.0
        budget_breakdown = {}
        
        for campaign in campaigns:
            budget = campaign.get("budget", 0)
            if isinstance(budget, (int, float)) and budget > 0:
                total_budget += budget
                platform = campaign.get("platform", "unknown")
                if platform not in budget_breakdown:
                    budget_breakdown[platform] = 0.0
                budget_breakdown[platform] += budget
        
        return {
            "total_budget": total_budget,
            "budget_breakdown": budget_breakdown,
            "campaign_count": len(campaigns),
            "average_budget": total_budget / len(campaigns) if campaigns else 0.0,
            "normalized_at": datetime.utcnow().isoformat()
        }
    
    def _calculate_workspace_quality(self, discovery_result: Dict[str, Any], validation_result: Dict[str, Any]) -> float:
        """Calculate overall workspace quality score."""
        discovery_score = 1.0 if discovery_result.get("discovered_files") else 0.0
        validation_score = validation_result.get("overall_score", 0.0)
        
        # Weight discovery and validation equally
        return (discovery_score + validation_score) / 2.0
    
    def _generate_workspace_recommendations(self, discovery_result: Dict[str, Any], validation_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations for workspace improvement."""
        recommendations = []
        
        file_count = len(discovery_result.get("discovered_files", []))
        if file_count == 0:
            recommendations.append("No campaign files found. Consider organizing campaign data in Google Drive.")
        elif file_count < 3:
            recommendations.append("Limited campaign files found. Consider consolidating campaign data.")
        
        validation_score = validation_result.get("overall_score", 0.0)
        if validation_score < 0.5:
            recommendations.append("Data quality is low. Review and clean up campaign data structure.")
        elif validation_score < 0.8:
            recommendations.append("Data quality could be improved. Consider standardizing field names and formats.")
        
        errors = validation_result.get("errors", [])
        if errors:
            recommendations.append(f"Found {len(errors)} data validation errors that need attention.")
        
        if not recommendations:
            recommendations.append("Workspace appears well-organized and data quality is good.")
        
        return recommendations

    # Legacy compatibility methods for existing code
    async def _extract_google_sheets(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy method - delegates to new handler."""
        return await self._handle_extract_google_sheets(task_data)
    
    async def _parse_campaign_file(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse campaign files using FileParser."""
        file_path = task_data.get("file_path")
        file_type = task_data.get("file_type", "auto")
        
        if not file_path:
            raise ValueError("File path is required")
        
        # Parse the file
        parsed_data = await self.file_parser.parse_file(file_path, file_type)
        
        # Validate parsed data
        validation_result = await self.data_validator.validate_campaign_data(parsed_data)
        
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
        """Legacy method - delegates to new handler."""
        return await self._handle_validate_data(task_data)
    
    async def _manage_workspace(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage workspace operations."""
        operation = task_data.get("operation")
        operation_data = task_data.get("operation_data", {})
        
        if not operation:
            raise ValueError("Operation is required")
        
        # Execute operation using workspace manager
        result = await self.workspace_manager.execute_operation(operation, operation_data)
        
        return {
            "operation": operation,
            "result": result,
            "metadata": {
                "operation_time": datetime.utcnow().isoformat()
            }
        } 