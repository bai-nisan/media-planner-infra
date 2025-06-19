"""
Core configuration settings for the Media Planning Platform API.

Uses Pydantic Settings for environment-based configuration management
following FastAPI best practices.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application Info
    PROJECT_NAME: str = "Media Planning Platform API"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "FastAPI backend service for comprehensive media planning platform"
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        # Local development URLs
        "http://localhost:3000",  # React frontend (development)
        "http://localhost:8080",  # Alternative frontend port
        "https://localhost:3000", # HTTPS development
        
        # Lovable platform URLs
        "https://lovable.dev",     # Lovable platform domain
        "https://*.lovable.dev",   # Lovable subdomains
        "https://*.lovable.app",   # Lovable app domains
        
        # Specific Lovable project URL (from README)
        "https://lovable.dev/projects/ba9f62a7-06d2-415f-95fa-954218aa84e4",
        
        # Additional development and staging environments
        "https://staging.lovable.dev",
        "https://preview.lovable.dev",
    ]
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from environment variable."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database Configuration
    DATABASE_URL: Optional[str] = None
    
    # Supabase Configuration
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_ANON_KEY: str = "placeholder_anon_key"
    SUPABASE_SERVICE_ROLE_KEY: str = "placeholder_service_key"
    SUPABASE_JWT_SECRET: str = "placeholder_jwt_secret"
    
    # Redis Configuration (for caching)
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security Configuration
    SECRET_KEY: str = "dev_secret_key_replace_in_production_min_32_chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    @validator("DEBUG", pre=True)
    def parse_debug(cls, v):
        """Parse debug flag from environment."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    
    # Performance Configuration
    MAX_CONNECTIONS_COUNT: int = 10
    MIN_CONNECTIONS_COUNT: int = 10
    
    # Multi-tenant Configuration
    DEFAULT_TENANT_ID: str = "default"
    TENANT_HEADER_NAME: str = "X-Tenant-ID"
    
    # File Upload Configuration
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER: str = "uploads"
    
    # Media Planning Specific Configuration
    DEFAULT_CAMPAIGN_DURATION_DAYS: int = 30
    MAX_CAMPAIGN_BUDGET: float = 1000000.0
    MIN_CAMPAIGN_BUDGET: float = 100.0
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Temporal Configuration
    TEMPORAL_HOST: str = "localhost"
    TEMPORAL_PORT: int = 7233
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TLS_ENABLED: bool = False
    TEMPORAL_DATA_CONVERTER: str = "default"  # Options: default, json, protobuf
    
    # Temporal Worker Configuration
    TEMPORAL_TASK_QUEUE_INTEGRATION: str = "media-planner-integration"
    TEMPORAL_TASK_QUEUE_SYNC: str = "media-planner-sync"
    TEMPORAL_TASK_QUEUE_PLANNING: str = "media-planner-planning"
    MAX_CONCURRENT_WORKFLOW_TASKS: int = 1000
    MAX_CONCURRENT_ACTIVITY_TASKS: int = 1000
    
    # Temporal Workflow Configuration
    DEFAULT_WORKFLOW_TIMEOUT_HOURS: int = 24
    DEFAULT_ACTIVITY_TIMEOUT_MINUTES: int = 10
    WORKFLOW_EXECUTION_RETENTION_DAYS: int = 7
    
    # Google API Configuration
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CLIENT_SECRETS_FILE: str = "config/client_secrets.json"
    GOOGLE_CREDENTIALS_FILE: str = "config/google_credentials.json"
    GOOGLE_APPLICATION_NAME: str = "Media Planning Platform"
    
    # Google Ads API Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = None
    GOOGLE_ADS_CUSTOMER_ID: Optional[str] = None
    GOOGLE_ADS_CONFIG_FILE: str = "config/google-ads.yaml"
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: Optional[str] = None  # Manager account ID
    
    # AI/LLM API Configuration
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    PERPLEXITY_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None
    OLLAMA_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/api"
    
    # LangGraph/LangSmith Configuration
    LANGSMITH_API_KEY: Optional[str] = None
    LANGGRAPH_AUTH_TYPE: str = "noop"  # For LangGraph Studio development
    POSTGRES_URI: Optional[str] = None  # For LangGraph checkpointing
    REDIS_URI: Optional[str] = None  # For LangGraph caching

    # Google API Scopes
    GOOGLE_DRIVE_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.file"
    ]
    GOOGLE_SHEETS_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    GOOGLE_ADS_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/adwords"
    ]
    
    @property
    def all_google_scopes(self) -> List[str]:
        """Get all Google API scopes combined."""
        return self.GOOGLE_DRIVE_SCOPES + self.GOOGLE_SHEETS_SCOPES + self.GOOGLE_ADS_SCOPES
    
    @property
    def temporal_address(self) -> str:
        """Get the full Temporal server address."""
        return f"{self.TEMPORAL_HOST}:{self.TEMPORAL_PORT}"
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance - useful for dependency injection."""
    return settings 