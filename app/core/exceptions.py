"""
Custom exception classes for the Media Planning Platform API.

Defines application-specific exceptions for better error handling
and user feedback across the AI workflow orchestration system.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class MediaPlannerException(Exception):
    """Base exception class for Media Planner application."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "GENERAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class AIWorkflowError(MediaPlannerException):
    """Base exception for AI workflow-related errors."""
    
    def __init__(
        self, 
        message: str, 
        workflow_id: Optional[str] = None,
        error_code: str = "AI_WORKFLOW_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.workflow_id = workflow_id
        details = details or {}
        if workflow_id:
            details["workflow_id"] = workflow_id
        super().__init__(message, error_code, details)


class ModelProcessingError(AIWorkflowError):
    """Exception raised when AI model processing fails."""
    
    def __init__(
        self, 
        message: str, 
        model_name: Optional[str] = None,
        workflow_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.model_name = model_name
        details = details or {}
        if model_name:
            details["model_name"] = model_name
        super().__init__(
            message, 
            workflow_id, 
            "MODEL_PROCESSING_ERROR", 
            details
        )


class DataValidationError(MediaPlannerException):
    """Exception raised when data validation fails."""
    
    def __init__(
        self, 
        message: str, 
        field_name: Optional[str] = None,
        validation_errors: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.field_name = field_name
        self.validation_errors = validation_errors or []
        details = details or {}
        if field_name:
            details["field_name"] = field_name
        if validation_errors:
            details["validation_errors"] = validation_errors
        super().__init__(message, "DATA_VALIDATION_ERROR", details)


class AuthenticationError(MediaPlannerException):
    """Exception raised when authentication fails."""
    
    def __init__(
        self, 
        message: str = "Authentication failed",
        auth_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.auth_method = auth_method
        details = details or {}
        if auth_method:
            details["auth_method"] = auth_method
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class AuthorizationError(MediaPlannerException):
    """Exception raised when authorization fails."""
    
    def __init__(
        self, 
        message: str = "Insufficient permissions",
        required_scope: Optional[str] = None,
        user_scopes: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.required_scope = required_scope
        self.user_scopes = user_scopes or []
        details = details or {}
        if required_scope:
            details["required_scope"] = required_scope
        if user_scopes:
            details["user_scopes"] = user_scopes
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class DatabaseError(MediaPlannerException):
    """Exception raised when database operations fail."""
    
    def __init__(
        self, 
        message: str, 
        operation: Optional[str] = None,
        table_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.table_name = table_name
        details = details or {}
        if operation:
            details["operation"] = operation
        if table_name:
            details["table_name"] = table_name
        super().__init__(message, "DATABASE_ERROR", details)


class ExternalServiceError(MediaPlannerException):
    """Exception raised when external service calls fail."""
    
    def __init__(
        self, 
        message: str, 
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.service_name = service_name
        self.status_code = status_code
        details = details or {}
        if service_name:
            details["service_name"] = service_name
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)


class WebSocketConnectionError(MediaPlannerException):
    """Exception raised when WebSocket connection operations fail."""
    
    def __init__(
        self, 
        message: str, 
        client_id: Optional[str] = None,
        connection_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.client_id = client_id
        self.connection_state = connection_state
        details = details or {}
        if client_id:
            details["client_id"] = client_id
        if connection_state:
            details["connection_state"] = connection_state
        super().__init__(message, "WEBSOCKET_CONNECTION_ERROR", details)


class CampaignProcessingError(AIWorkflowError):
    """Exception raised when campaign processing fails."""
    
    def __init__(
        self, 
        message: str, 
        campaign_id: Optional[str] = None,
        processing_stage: Optional[str] = None,
        workflow_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.campaign_id = campaign_id
        self.processing_stage = processing_stage
        details = details or {}
        if campaign_id:
            details["campaign_id"] = campaign_id
        if processing_stage:
            details["processing_stage"] = processing_stage
        super().__init__(
            message, 
            workflow_id, 
            "CAMPAIGN_PROCESSING_ERROR", 
            details
        )


class BudgetCalculationError(MediaPlannerException):
    """Exception raised when budget calculations fail."""
    
    def __init__(
        self, 
        message: str, 
        budget_amount: Optional[float] = None,
        calculation_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.budget_amount = budget_amount
        self.calculation_type = calculation_type
        details = details or {}
        if budget_amount is not None:
            details["budget_amount"] = budget_amount
        if calculation_type:
            details["calculation_type"] = calculation_type
        super().__init__(message, "BUDGET_CALCULATION_ERROR", details)


# HTTP Exception factory functions
def create_http_exception(
    exc: MediaPlannerException,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    include_details: bool = False
) -> HTTPException:
    """
    Create an HTTPException from a MediaPlannerException.
    
    Args:
        exc: The custom exception
        status_code: HTTP status code
        include_details: Whether to include error details in response
        
    Returns:
        HTTPException instance
    """
    error_response = {
        "error_code": exc.error_code,
        "message": exc.message
    }
    
    if include_details and exc.details:
        error_response["details"] = exc.details
    
    return HTTPException(
        status_code=status_code,
        detail=error_response
    )


# Status code mappings for different exception types
EXCEPTION_STATUS_CODES = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    DataValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
    WebSocketConnectionError: status.HTTP_400_BAD_REQUEST,
    ModelProcessingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    AIWorkflowError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    CampaignProcessingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    BudgetCalculationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    MediaPlannerException: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def get_exception_status_code(exc: MediaPlannerException) -> int:
    """
    Get the appropriate HTTP status code for an exception.
    
    Args:
        exc: The exception instance
        
    Returns:
        HTTP status code
    """
    return EXCEPTION_STATUS_CODES.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR) 