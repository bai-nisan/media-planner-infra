"""
Media Planning Platform API

FastAPI backend service for comprehensive media planning platform.
Entry point for the application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.api.v1.api import api_router
from app.middleware.error_handling import ErrorHandlingMiddleware, create_exception_handlers
from app.core.exceptions import MediaPlannerException

# Create FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for comprehensive media planning platform with multi-tenant architecture, real-time analytics, and campaign management",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json"
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
    return {
        "status": "healthy",
        "service": "media-planner-api",
        "version": settings.VERSION
    }


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