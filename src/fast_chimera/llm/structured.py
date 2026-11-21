"""Responsibility: ask the model for JSON and return a validated pydantic object."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from fast_chimera.core.exceptions import LlmResponseError
from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.json_extraction import extract_json

T = TypeVar("T", bound=BaseModel)


async def generate_model(
    client: LlmClient,
    model_class: type[T],
    prompt: str,
    system_instruction: str,
    *,
    max_attempts: int = 3,
) -> T:
    """Ask for JSON, validate it, and when invalid re-ask with the validation error attached."""
    schema = json.dumps(model_class.model_json_schema(), indent=2)
    system = f"{system_instruction}\n\nReturn ONLY a JSON object that validates against this JSON Schema:\n{schema}"

    current_prompt = prompt
    last_error = ""
    for _ in range(max_attempts):
        answer = await client.generate_text(current_prompt, system, json_mode=True)
        try:
            return model_class.model_validate(extract_json(answer))
        except ValueError as error:  # covers JSONDecodeError and pydantic's ValidationError
            last_error = str(error)[:800]
            current_prompt = f"{prompt}\n\nYour previous answer was invalid:\n{last_error}\nReturn the corrected JSON only."

    raise LlmResponseError(f"The model did not return valid {model_class.__name__} JSON: {last_error}")
