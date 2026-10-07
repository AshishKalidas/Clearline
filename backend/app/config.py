"""Environment-backed settings. Live providers are always opt-in."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and safety configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/clearline.db"
    agent_database_url: str | None = None
    api_key: str = "clearline-local-demo"
    llm_provider: Literal["stub", "claude", "mimo"] = "stub"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    mimo_base_url: str = ""
    mimo_api_key: str = ""
    mimo_model: str = ""
    embedder: Literal["local", "hash"] = "local"
    retrieval_enabled: bool = True
    auto_confidence: float = Field(default=0.90, ge=0, le=1)
    auto_limit_cents: int = Field(default=500000, ge=0)
    pop_retention_days: int = Field(default=30, ge=1)
    pop_directory: Path = Path("data/pops")
    max_upload_bytes: int = Field(default=5_000_000, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()
