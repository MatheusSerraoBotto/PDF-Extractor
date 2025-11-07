"""Application settings loaded from environment variables via Pydantic."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values for the application."""

    model_config = SettingsConfigDict(
        env_file=(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    # Environment
    env: str = Field(default="development")
    debug: bool = Field(default=False, description="Enable debug mode")
    testing: bool = Field(default=False, description="Enable testing mode")
    log_level: str = Field(default="INFO")

    # Server Configuration
    workers: int = Field(default=4, description="Number of Uvicorn workers")
    max_concurrent_requests: int = Field(
        default=100, description="Maximum concurrent requests"
    )
    request_timeout: int = Field(default=300, description="Request timeout in seconds")

    # CORS Configuration
    allowed_origins: str = Field(
        default="http://localhost,http://localhost:80,http://localhost:5173,http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    # Redis Configuration
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: Optional[str] = Field(
        default=None, description="Redis password for authentication"
    )
    redis_ssl: bool = Field(
        default=False, description="Enable SSL/TLS for Redis connections"
    )
    redis_max_connections: int = Field(
        default=20, description="Maximum Redis connection pool size"
    )
    redis_socket_timeout: int = Field(default=5, description="Redis socket timeout")
    redis_socket_connect_timeout: int = Field(
        default=5, description="Redis connection timeout"
    )

    # OpenAI LLM Configuration
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key (required)"
    )
    llm_model: str = Field(
        default="gpt-5-mini",
        description="OpenAI model identifier",
    )
    llm_max_output_tokens: int = Field(
        default=800, description="Maximum tokens in LLM output"
    )
    openai_timeout: int = Field(default=60, description="OpenAI API timeout in seconds")
    openai_max_retries: int = Field(default=3, description="OpenAI API max retries")

    # File Configuration
    pdf_base_path: Optional[str] = Field(
        default=None,
        description="Base directory for locating PDF files when requests provide relative paths.",
    )

    # Batch Processing Configuration
    max_concurrent_extractions: int = Field(
        default=10,
        description="Maximum number of concurrent PDF extractions in batch mode",
    )
    max_batch_size: int = Field(
        default=100000,
        description="Maximum number of items allowed in a single batch request",
    )

    # Monitoring & Observability
    sentry_dsn: Optional[str] = Field(
        default=None, description="Sentry DSN for error tracking"
    )
    datadog_api_key: Optional[str] = Field(
        default=None, description="Datadog API key for monitoring"
    )

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", description="AWS region")
    secrets_manager_name: Optional[str] = Field(
        default=None, description="AWS Secrets Manager secret name"
    )

    # Security
    api_key_header: str = Field(
        default="X-API-Key", description="Header name for API key authentication"
    )
    rate_limit_per_minute: int = Field(
        default=60, description="Rate limit requests per minute per IP"
    )

    @computed_field
    @property
    def is_production(self) -> bool:
        """True when running in production mode."""
        return self.env.lower() == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.env.lower() == "development"

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: str) -> str:
        """Validate CORS origins format."""
        if not v:
            raise ValueError("allowed_origins cannot be empty")
        # Split and strip whitespace
        origins = [origin.strip() for origin in v.split(",")]
        return ",".join(origins)


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Single settings object importable by application modules
settings = get_settings()
