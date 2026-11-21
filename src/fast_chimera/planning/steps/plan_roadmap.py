from __future__ import annotations

from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.structured import generate_model
from fast_chimera.planning.prompts.roadmap import build_roadmap_prompt
from fast_chimera.planning.schemas import FeatureCatalog, Roadmap


class RoadmapPlanning:
    """Question 2: in which order, and in how many phases, should it be built?"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    async def run(self, request: str, catalog: FeatureCatalog, mode: str, project_symbols: str) -> Roadmap:
        prompt = build_roadmap_prompt(request, catalog, mode, project_symbols)
        roadmap = await generate_model(self._llm, Roadmap, prompt.user, prompt.system)
        return roadmap.renumbered()
