"""Responsibility: talk to the Gemini REST API.

Pattern: Adapter. It adapts Gemini's HTTP API to our own `LlmClient` interface, so the rest
of the package never knows which provider is behind it. The small pieces it uses
(request body, response parsing, retry policy) live in their own modules.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from fast_chimera.config import Settings, get_settings
from fast_chimera.core.exceptions import LlmAPIError
from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.request import build_request
from fast_chimera.llm.response import error_message, extract_text, retry_after_seconds
from fast_chimera.llm.retry import RetryPolicy

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient(LlmClient):
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings or get_settings()
        self._retry = retry_policy or RetryPolicy(max_attempts=self._settings.chimera_retry_attempts)
        self._sleep = sleep
        self._url = f"{BASE_URL}/{self._settings.chimera_gemini_model}:generateContent"
        # The key travels in a header, never in the URL (URLs end up in logs and tracebacks).
        self._http = httpx.AsyncClient(
            timeout=self._settings.chimera_timeout,
            transport=transport,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._settings.gemini_api_key.get_secret_value(),
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        if temperature is None:
            temperature = self._settings.chimera_temperature
        body = build_request(prompt, system_instruction, json_mode=json_mode, temperature=temperature)
        data = await self._post_with_retries(body)
        return extract_text(data)

    async def _post_with_retries(self, body: dict[str, Any]) -> dict[str, Any]:
        attempts = self._retry.max_attempts
        last_problem = "unknown error"

        for attempt in range(1, attempts + 1):
            retry_after: float | None = None
            try:
                response = await self._http.post(self._url, json=body)
            except httpx.TransportError as error:
                last_problem = f"network error ({type(error).__name__})"
            else:
                if response.is_success:
                    return response.json()
                last_problem = f"HTTP {response.status_code}: {error_message(response)}"
                if not self._retry.is_retryable(response.status_code):
                    raise LlmAPIError(f"Gemini API error ({last_problem})")
                retry_after = retry_after_seconds(response)

            if attempt < attempts:
                await self._sleep(self._retry.delay_before_next_attempt(attempt, retry_after))

        raise LlmAPIError(f"Gemini API error after {attempts} attempt(s): {last_problem}")
