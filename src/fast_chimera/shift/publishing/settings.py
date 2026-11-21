"""Responsibility: read the SHIFT_* settings. Separate from the Gemini settings on purpose:
`shift` must work without any LLM key."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fast_chimera.core.exceptions import ShiftConfigError
from fast_chimera.shift.publishing.url_policy import validate_server_url


class ShiftSettings(BaseSettings):
    shift_server_url: str | None = None
    shift_api_token: SecretStr | None = None
    shift_timeout: float = 30.0
    shift_retry_attempts: int = 3
    shift_allow_insecure: bool = False

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    @field_validator("shift_server_url", "shift_api_token", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    def server_url(self, override: str | None = None) -> str | None:
        """The validated URL to send to, or None when nothing is configured."""
        url = (override or self.shift_server_url or "").strip()
        if not url:
            return None
        return validate_server_url(url, allow_insecure=self.shift_allow_insecure)


def load_shift_settings(project_root: Path) -> ShiftSettings:
    """Reads SHIFT_* from the process environment, then the project's `.env`, then the current folder's `.env`."""
    env_files = tuple(dict.fromkeys([Path(project_root) / ".env", Path.cwd() / ".env"]))
    try:
        return ShiftSettings(_env_file=env_files)  # type: ignore[call-arg]
    except ValidationError as error:
        names = ", ".join(sorted({str(item["loc"][0]).upper() for item in error.errors()}))
        raise ShiftConfigError(f"Invalid settings: {names}") from error
