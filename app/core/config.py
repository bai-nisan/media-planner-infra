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
        "http://localhost:3000",  # React frontend (development)
        "http://localhost:8080",  # Alternative frontend port
        "https://localhost:3000", # HTTPS development
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
    SUPABASE_KEY: str = "placeholder_key"
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