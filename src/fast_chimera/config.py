from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from fast_chimera.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Settings read from environment variables or a .env file in the working directory."""

    gemini_api_key: SecretStr
    chimera_gemini_model: str = "gemini-3.5-flash-lite"
    chimera_retry_attempts: int = 4
    chimera_timeout: float = 120.0
    chimera_temperature: float = 0.2
    # Files per checkpoint: after each batch the project is import-checked (and repaired).
    chimera_batch_size: int = 4
    chimera_repair_attempts: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Lazy, cached settings: nothing is read at import time, so `--help` always works."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        missing = sorted({str(err["loc"][0]).upper() for err in e.errors()})
        raise ConfigurationError(
            f"Missing or invalid settings: {', '.join(missing)}. Set them as environment variables or in a .env file."
        ) from e
