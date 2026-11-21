"""Responsibility: build the JSON body of a Gemini `generateContent` request."""

from __future__ import annotations

from typing import Any


def build_request(
    prompt: str,
    system_instruction: str | None,
    *,
    json_mode: bool,
    temperature: float,
) -> dict[str, Any]:
    generation_config: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    return body
