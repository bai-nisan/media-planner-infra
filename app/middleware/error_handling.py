"""
Error handling middleware for the Media Planning Platform API.

Provides comprehensive error handling with consistent JSON responses,
structured logging, and proper HTTP status codes.
"""

import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, Union
import logging

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from app.core.exceptions import (
    MediaPlannerException,
    get_exception_status_code,
    EXCEPTION_STATUS_CODES
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response structure."""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        request_id: str,
        timestamp: str,
        details: Dict[str, Any] = None,
        status_code: int = 500
    ):
        self.error_code = error_code
        self.message = message
        self.request_id = request_id
        self.timestamp = timestamp
        self.details = details or {}
        self.status_code = status_code
    
    def to_dict(self, include_details: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        response = {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "request_id": self.request_id,
            "timestamp": self.timestamp
        }
        
        if include_details and self.details:
            response["details"] = self.details
            
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle all exceptions and provide consistent error responses.
    
    Features:
    - Catches all unhandled exceptions
    - Provides structured JSON error responses
    - Logs errors with appropriate severity levels
    - Includes request correlation IDs
    - Handles both sync and async exceptions
    """
    
    def __init__(self, app, include_details_in_prod: bool = False):
        super().__init__(app)
        self.include_details_in_prod = include_details_in_prod
    
    async def dispatch(self, request: Request, call_next):
        """
        Process the request and handle any exceptions.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain
            
        Returns:
            Response object
        """
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            # Process the request
            response = await call_next(request)
            return response
            
        except Exception as exc:
            # Handle the exception and return error response
            return await self._handle_exception(request, exc, request_id)
    
    async def _handle_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str
    ) -> JSONResponse:
        """
        Handle specific exception types and create appropriate responses.
        
        Args:
            request: The request that caused the exception
            exc: The exception that was raised
            request_id: Unique request identifier
            
        Returns:
            JSONResponse with error details
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Log request context
        request_context = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": getattr(request.client, 'host', 'unknown'),
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        # Handle different exception types
        if isinstance(exc, MediaPlannerException):
            return await self._handle_custom_exception(exc, request_context, timestamp)
        elif isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, request_context, timestamp)
        elif isinstance(exc, RequestValidationError):
            return await self._handle_validation_error(exc, request_context, timestamp)
        elif isinstance(exc, ValidationError):
            return await self._handle_pydantic_validation_error(exc, request_context, timestamp)
        else:
            return await self._handle_unexpected_exception(exc, request_context, timestamp)
    
    async def _handle_custom_exception(
        self, 
        exc: MediaPlannerException, 
        request_context: Dict[str, Any],
        timestamp: str
    ) -> JSONResponse:
        """Handle custom MediaPlannerException instances."""
        status_code = get_exception_status_code(exc)
        
        # Log with appropriate level based on status code
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        
        logger.log(
            log_level,
            f"Custom exception: {exc.error_code}",
            extra={
                "exception_type": type(exc).__name__,
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                **request_context
            }
        )
        
        error_response = ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            request_id=request_context["request_id"],
            timestamp=timestamp,
            details=exc.details,
            status_code=status_code
        )
        
        include_details = self._should_include_details(status_code)
        
        return JSONResponse(
            status_code=status_code,
            content=error_response.to_dict(include_details=include_details)
        )
    
    async def _handle_http_exception(
        self, 
        exc: HTTPException, 
        request_context: Dict[str, Any],
        timestamp: str
    ) -> JSONResponse:
        """Handle FastAPI HTTPException instances."""
        logger.warning(
            f"HTTP exception: {exc.status_code}",
            extra={
                "exception_type": "HTTPException",
                "status_code": exc.status_code,
                "detail": exc.detail,
                **request_context
            }
        )
        
        error_response = ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail) if exc.detail else "HTTP Error",
            request_id=request_context["request_id"],
            timestamp=timestamp,
            status_code=exc.status_code
        )
        
        include_details = self._should_include_details(exc.status_code)
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.to_dict(include_details=include_details)
        )
    
    async def _handle_validation_error(
        self, 
        exc: RequestValidationError, 
        request_context: Dict[str, Any],
        timestamp: str
    ) -> JSONResponse:
        """Handle FastAPI request validation errors."""
        logger.warning(
            "Request validation error",
            extra={
                "exception_type": "RequestValidationError",
                "errors": exc.errors(),
                **request_context
            }
        )
        
        error_response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            request_id=request_context["request_id"],
            timestamp=timestamp,
            details={"validation_errors": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.to_dict(include_details=True)
        )
    
    async def _handle_pydantic_validation_error(
        self, 
        exc: ValidationError, 
        request_context: Dict[str, Any],
        timestamp: str
    ) -> JSONResponse:
        """Handle Pydantic model validation errors."""
        logger.warning(
            "Pydantic validation error",
            extra={
                "exception_type": "ValidationError",
                "errors": exc.errors(),
                **request_context
            }
        )
        
        error_response = ErrorResponse(
            error_code="PYDANTIC_VALIDATION_ERROR",
            message="Data validation failed",
            request_id=request_context["request_id"],
            timestamp=timestamp,
            details={"validation_errors": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.to_dict(include_details=True)
        )
    
    async def _handle_unexpected_exception(
        self, 
        exc: Exception, 
        request_context: Dict[str, Any],
        timestamp: str
    ) -> JSONResponse:
        """Handle unexpected/unhandled exceptions."""
        logger.error(
            f"Unexpected exception: {type(exc).__name__}",
            extra={
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                **request_context
            }
        )
        
        error_response = ErrorResponse(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            request_id=request_context["request_id"],
            timestamp=timestamp,
            details={"exception_type": type(exc).__name__} if settings.DEBUG else {},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        include_details = self._should_include_details(status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.to_dict(include_details=include_details)
        )
    
    def _should_include_details(self, status_code: int) -> bool:
        """
        Determine whether to include error details in the response.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            True if details should be included
        """
        # Always include details in debug mode
        if settings.DEBUG:
            return True
        
        # Include details for client errors (4xx) but not server errors (5xx) in production
        # unless explicitly configured
        if 400 <= status_code < 500:
            return True
        
        return self.include_details_in_prod


# Global exception handlers for use with FastAPI app
def create_exception_handlers() -> Dict[Union[int, type], Any]:
    """
    Create a dictionary of exception handlers for FastAPI.
    
    Returns:
        Dictionary mapping exception types to handler functions
    """
    
    async def media_planner_exception_handler(request: Request, exc: MediaPlannerException):
        """Handle MediaPlannerException instances."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        status_code = get_exception_status_code(exc)
        
        error_response = ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            request_id=request_id,
            timestamp=timestamp,
            details=exc.details,
            status_code=status_code
        )
        
        include_details = settings.DEBUG or (400 <= status_code < 500)
        
        return JSONResponse(
            status_code=status_code,
            content=error_response.to_dict(include_details=include_details)
        )
    
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        
        error_response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            request_id=request_id,
            timestamp=timestamp,
            details={"validation_errors": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.to_dict(include_details=True)
        )
    
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        
        error_response = ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail) if exc.detail else "HTTP Error",
            request_id=request_id,
            timestamp=timestamp,
            status_code=exc.status_code
        )
        
        include_details = settings.DEBUG or (400 <= exc.status_code < 500)
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.to_dict(include_details=include_details)
        )
    
    return {
        MediaPlannerException: media_planner_exception_handler,
        RequestValidationError: validation_exception_handler,
        HTTPException: http_exception_handler,
    } 