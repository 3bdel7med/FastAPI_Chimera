"""Responsibility: turn a Gemini response into plain text, or a clear error."""

from __future__ import annotations

from typing import Any

import httpx

from fast_chimera.core.exceptions import LlmAPIError


def extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise LlmAPIError(f"Gemini returned no candidates (blocked?): {data.get('promptFeedback')}")

    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))

    if finish_reason == "MAX_TOKENS":
        raise LlmAPIError("Gemini response was truncated (MAX_TOKENS); try a smaller batch or phase.")
    if not text.strip():
        raise LlmAPIError(f"Gemini returned an empty response (finishReason={finish_reason}).")
    return text


def error_message(response: httpx.Response) -> str:
    """The server's own error message, shortened. Never includes request headers (the API key)."""
    try:
        return str(response.json()["error"]["message"])[:500]
    except (ValueError, KeyError, TypeError):
        return response.text[:300]


def retry_after_seconds(response: httpx.Response) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None
