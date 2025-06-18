"""
Media Planning Platform API

FastAPI backend service for comprehensive media planning platform.
Entry point for the application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.api.v1.api import api_router
from app.middleware.error_handling import ErrorHandlingMiddleware, create_exception_handlers
from app.core.exceptions import MediaPlannerException
from app.temporal.client import get_temporal_client, close_temporal_client
from app.services.temporal_service import TemporalService
from app.services.langgraph.agent_service import get_agent_service
from app.dependencies import get_temporal_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle, including Temporal client setup.
    
    This context manager handles the startup and shutdown of the Temporal client
    and other resources that need proper lifecycle management.
    """
    logger.info("Starting up Media Planning Platform API")
    
    try:
        # Initialize Temporal client on startup
        temporal_client = await get_temporal_client(settings)
        logger.info("Temporal client connected successfully")
        
        # Store temporal client in app state
        app.state.temporal_client = temporal_client
        app.state.temporal_service = TemporalService(temporal_client, settings)
        
        # Initialize LangGraph agent service
        try:
            agent_service = await get_agent_service()
            app.state.agent_service = agent_service
            logger.info("LangGraph agent service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent service: {e}")
            # Continue without agent service for now - this allows the app to start
            # even if agents are not fully configured
            app.state.agent_service = None
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down Media Planning Platform API")
        try:
            # Shutdown agent service if initialized
            if hasattr(app.state, 'agent_service') and app.state.agent_service:
                await app.state.agent_service.shutdown()
                logger.info("Agent service shutdown completed")
            
            await close_temporal_client()
            logger.info("Temporal client disconnected successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Create FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for comprehensive media planning platform with multi-tenant architecture, real-time analytics, and campaign management",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan  # Add lifecycle management
)

# Add error handling middleware
app.add_middleware(
    ErrorHandlingMiddleware,
    include_details_in_prod=False  # Set to True if you want detailed errors in production
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add global exception handlers
exception_handlers = create_exception_handlers()
for exception_type, handler in exception_handlers.items():
    app.add_exception_handler(exception_type, handler)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from datetime import datetime
    
    basic_health = {
        "status": "healthy",
        "service": "media-planner-api",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Try to include Temporal health status
    try:
        if hasattr(app.state, 'temporal_service') and app.state.temporal_service:
            temporal_health = await app.state.temporal_service.health_check()
            basic_health["temporal"] = temporal_health
        else:
            basic_health["temporal"] = {
                "status": "not_initialized",
                "message": "Temporal service not yet initialized"
            }
    except Exception as e:
        logger.warning(f"Could not get Temporal health status: {e}")
        basic_health["temporal"] = {
            "status": "unavailable",
            "error": str(e)
        }
    
    return basic_health


@app.get("/health/temporal")
async def temporal_health_check(
    temporal_service: TemporalService = Depends(get_temporal_service)
):
    """Detailed Temporal health check endpoint."""
    return await temporal_service.health_check()


@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Media Planning Platform API",
        "version": settings.VERSION,
        "docs": "/api/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 