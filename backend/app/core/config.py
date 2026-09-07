from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Industrial Maintenance Copilot"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    answer_generator: Literal["extractive", "openai"] = "extractive"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=30.0, gt=0.0, le=120.0)
    agent_max_steps: int = Field(default=3, ge=1, le=3)
    chunk_store_path: Path = Path("data/processed/documents.sqlite3")
    api_access_token: SecretStr | None = None
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value == "/" or "?" in value or "#" in value:
            raise ValueError("api_prefix must be an absolute non-root URL path")
        return value.rstrip("/")

    @model_validator(mode="after")
    def protect_production_api(self) -> "Settings":
        token = self.api_access_token.get_secret_value().strip() if self.api_access_token else ""
        if self.app_env == "production" and len(token) < 24:
            raise ValueError("production requires an API_ACCESS_TOKEN of at least 24 characters")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
