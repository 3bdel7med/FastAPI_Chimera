"""Pattern: Facade. One simple object for the three planning questions; each question is its
own small class in `steps/`."""

from __future__ import annotations

from fast_chimera.core.interfaces import LlmClient
from fast_chimera.planning.prompts.phase import PhasePromptInput
from fast_chimera.planning.schemas import FeatureCatalog, PhasePlan, Roadmap
from fast_chimera.planning.steps.discover_features import FeatureDiscovery
from fast_chimera.planning.steps.plan_phase import PhasePlanning
from fast_chimera.planning.steps.plan_roadmap import RoadmapPlanning


class Planner:
    def __init__(self, llm: LlmClient) -> None:
        self._discovery = FeatureDiscovery(llm)
        self._roadmap = RoadmapPlanning(llm)
        self._phase = PhasePlanning(llm)

    async def discover_features(self, request: str) -> FeatureCatalog:
        return await self._discovery.run(request)

    async def create_roadmap(self, request: str, catalog: FeatureCatalog, *, mode: str = "build", project_symbols: str = "") -> Roadmap:
        return await self._roadmap.run(request, catalog, mode, project_symbols)

    async def plan_phase(self, data: PhasePromptInput) -> PhasePlan:
        return await self._phase.run(data)
