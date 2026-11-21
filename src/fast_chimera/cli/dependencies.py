"""Pattern: Factory functions. The CLI asks for its collaborators here instead of constructing them,
so tests can replace them (for example with a fake LLM) by patching one place."""

from __future__ import annotations

from fast_chimera.config import Settings
from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.gemini_client import GeminiClient
from fast_chimera.shift.publishing import ShiftPublisher, ShiftSettings


def create_llm_client(settings: Settings) -> LlmClient:
    return GeminiClient(settings)


def create_publisher(settings: ShiftSettings) -> ShiftPublisher:
    return ShiftPublisher(settings)
