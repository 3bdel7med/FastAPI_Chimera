from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LlmClient(ABC):
    """Provider-agnostic LLM interface (Dependency Inversion)."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Return the model's text answer. With json_mode the answer must be raw JSON."""

    async def aclose(self) -> None:
        """Release network resources. Default: nothing to release."""

    async def __aenter__(self) -> LlmClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()
