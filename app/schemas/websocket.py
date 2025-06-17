"""
WebSocket message schemas for real-time communication.

Defines the structure for messages sent between the FastAPI backend 
and frontend clients via WebSocket connections.
"""

from enum import Enum
from typing import Any, Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Types of WebSocket messages."""
    
    # Connection management
    CONNECTION_ACK = "connection_ack"
    CONNECTION_ERROR = "connection_error"
    
    # AI Workflow updates
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_PROGRESS = "workflow_progress"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    
    # Campaign analysis updates
    CAMPAIGN_ANALYSIS_STARTED = "campaign_analysis_started"
    CAMPAIGN_ANALYSIS_PROGRESS = "campaign_analysis_progress"
    CAMPAIGN_ANALYSIS_COMPLETED = "campaign_analysis_completed"
    
    # Research updates
    RESEARCH_STARTED = "research_started"
    RESEARCH_PROGRESS = "research_progress"
    RESEARCH_COMPLETED = "research_completed"
    
    # General notifications
    NOTIFICATION = "notification"
    ERROR = "error"


class WebSocketMessage(BaseModel):
    """Base WebSocket message schema."""
    
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    client_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class WorkflowStatusUpdate(BaseModel):
    """Schema for AI workflow status updates."""
    
    workflow_id: str
    workflow_type: str  # e.g., "campaign_analysis", "research", "optimization"
    status: str  # e.g., "started", "in_progress", "completed", "failed"
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    message: Optional[str] = None
    error_details: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


class CampaignAnalysisUpdate(BaseModel):
    """Schema for campaign analysis workflow updates."""
    
    campaign_id: str
    analysis_type: str  # e.g., "performance", "optimization", "audience"
    status: str
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    insights: Optional[List[str]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, float]] = None


class ResearchUpdate(BaseModel):
    """Schema for AI research task updates."""
    
    research_id: str
    query: str
    status: str
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    sources_found: Optional[int] = None
    findings: Optional[List[str]] = None
    summary: Optional[str] = None


class NotificationMessage(BaseModel):
    """Schema for general notifications."""
    
    title: str
    message: str
    severity: str = Field(default="info")  # info, warning, error, success
    action_url: Optional[str] = None
    dismissible: bool = True


class ConnectionAck(BaseModel):
    """Schema for connection acknowledgment."""
    
    client_id: str
    server_time: datetime = Field(default_factory=datetime.utcnow)
    session_id: str


class ErrorMessage(BaseModel):
    """Schema for error messages."""
    
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    recoverable: bool = True


# Message factory functions
def create_workflow_message(
    client_id: str,
    workflow_update: WorkflowStatusUpdate,
    message_type: MessageType = MessageType.WORKFLOW_PROGRESS
) -> WebSocketMessage:
    """Create a workflow status update message."""
    return WebSocketMessage(
        type=message_type,
        client_id=client_id,
        data=workflow_update.model_dump()
    )


def create_campaign_analysis_message(
    client_id: str,
    analysis_update: CampaignAnalysisUpdate,
    message_type: MessageType = MessageType.CAMPAIGN_ANALYSIS_PROGRESS
) -> WebSocketMessage:
    """Create a campaign analysis update message."""
    return WebSocketMessage(
        type=message_type,
        client_id=client_id,
        data=analysis_update.model_dump()
    )


def create_research_message(
    client_id: str,
    research_update: ResearchUpdate,
    message_type: MessageType = MessageType.RESEARCH_PROGRESS
) -> WebSocketMessage:
    """Create a research update message."""
    return WebSocketMessage(
        type=message_type,
        client_id=client_id,
        data=research_update.model_dump()
    )


def create_notification_message(
    client_id: str,
    notification: NotificationMessage
) -> WebSocketMessage:
    """Create a notification message."""
    return WebSocketMessage(
        type=MessageType.NOTIFICATION,
        client_id=client_id,
        data=notification.model_dump()
    )


def create_error_message(
    client_id: str,
    error: ErrorMessage
) -> WebSocketMessage:
    """Create an error message."""
    return WebSocketMessage(
        type=MessageType.ERROR,
        client_id=client_id,
        data=error.model_dump()
    )


def create_connection_ack(
    client_id: str,
    session_id: str
) -> WebSocketMessage:
    """Create a connection acknowledgment message."""
    return WebSocketMessage(
        type=MessageType.CONNECTION_ACK,
        client_id=client_id,
        data=ConnectionAck(
            client_id=client_id,
            session_id=session_id
        ).model_dump()
    ) 