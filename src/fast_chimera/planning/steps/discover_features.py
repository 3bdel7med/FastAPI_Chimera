from __future__ import annotations

from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.structured import generate_model
from fast_chimera.planning.prompts.discovery import build_discovery_prompt
from fast_chimera.planning.schemas import FeatureCatalog


class FeatureDiscovery:
    """Question 1: which features does a product like this have?"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    async def run(self, request: str) -> FeatureCatalog:
        prompt = build_discovery_prompt(request)
        return await generate_model(self._llm, FeatureCatalog, prompt.user, prompt.system)
