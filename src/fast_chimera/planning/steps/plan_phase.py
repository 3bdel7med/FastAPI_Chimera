from __future__ import annotations

from fast_chimera.core.interfaces import LlmClient
from fast_chimera.llm.structured import generate_model
from fast_chimera.planning.prompts.phase import PhasePromptInput, build_phase_prompt
from fast_chimera.planning.schemas import PhasePlan


class PhasePlanning:
    """Question 3: which files does THIS phase need? (asked once per phase, right before building it)"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    async def run(self, data: PhasePromptInput) -> PhasePlan:
        prompt = build_phase_prompt(data)
        return await generate_model(self._llm, PhasePlan, prompt.user, prompt.system)
