"""
Base Pydantic schemas for API responses.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model for all API endpoints."""
    
    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Human-readable message describing the result")
    data: Optional[Any] = Field(None, description="Response data payload")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": None
            }
        }


class ErrorResponse(BaseResponse):
    """Error response model."""
    
    success: bool = Field(False, description="Always false for error responses")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[dict] = Field(None, description="Additional error details")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "Operation failed",
                "error_code": "VALIDATION_ERROR",
                "details": {"field": "email", "issue": "Invalid format"}
            }
        } 