"""Application settings loaded from environment variables via Pydantic."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values for the application."""

    model_config = SettingsConfigDict(
        env_file=(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Redis
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)

    # LangChain / LLM
    openai_api_key: Optional[str] = Field(default=None)
    llm_provider: str = Field(default="langchain")
    langchain_cache: str = Field(default="redis")

    # Database
    database_url: str = Field(default="sqlite:////data/local.db")

    @computed_field
    @property
    def redis_dsn(self) -> str:
        """Return a redis:// connection string assembled from host and port."""
        return f"redis://{self.redis_host}:{self.redis_port}"

    @computed_field
    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.env.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Single settings object importable by application modules
settings = get_settings()
