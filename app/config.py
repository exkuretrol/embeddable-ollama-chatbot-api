from functools import lru_cache
from typing import Annotated

from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:3b", alias="OLLAMA_MODEL")
    api_key: str = Field(default="change-me", alias="API_KEY")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"], alias="ALLOWED_ORIGINS"
    )
    request_timeout: float = Field(default=60.0, gt=0, alias="REQUEST_TIMEOUT")
    health_timeout: float = Field(default=5.0, gt=0, alias="HEALTH_TIMEOUT")
    rate_limit_per_min: int = Field(default=30, ge=1, alias="RATE_LIMIT_PER_MIN")
    max_message_chars: int = Field(default=4000, ge=1, alias="MAX_MESSAGE_CHARS")
    max_history_items: int = Field(default=20, ge=1, alias="MAX_HISTORY_ITEMS")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        lowered = value.lower()
        if lowered not in {"dev", "prod"}:
            raise ValueError("APP_ENV must be 'dev' or 'prod'")
        return lowered

    @model_validator(mode="after")
    def validate_prod_api_key(self) -> "Settings":
        if self.app_env == "prod" and self.api_key == "change-me":
            raise ValueError("API_KEY must be changed in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
