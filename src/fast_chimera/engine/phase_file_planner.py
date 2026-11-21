"""Responsibility: ask the model which files a phase needs, then clean the answer up."""

from __future__ import annotations

from dataclasses import dataclass

from fast_chimera.core.exceptions import PlanningError
from fast_chimera.engine.context_factory import ContextFactory
from fast_chimera.engine.options import EngineOptions
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.planning.file_plan import drop_unusable_files, order_by_dependencies
from fast_chimera.planning.planner import Planner
from fast_chimera.planning.prompts.phase import PhasePromptInput
from fast_chimera.planning.schemas import FileSpec
from fast_chimera.state.models import BuildState, PhaseState


@dataclass(frozen=True)
class PlannedPhase:
    files: list[FileSpec]
    required_packages: list[str]
    dropped_paths: list[str]


class PhaseFilePlanner:
    def __init__(self, planner: Planner, writer: SafeWriter, contexts: ContextFactory, options: EngineOptions) -> None:
        self._planner = planner
        self._writer = writer
        self._contexts = contexts
        self._options = options

    async def plan(self, state: BuildState, phase: PhaseState) -> PlannedPhase:
        prompt_input = PhasePromptInput(
            request=state.prompt,
            catalog=state.catalog,
            roadmap_summary=self._roadmap_summary(state),
            phase=phase.outline,
            project_symbols=self._contexts.project_symbols(),
            mode=state.mode,
            allowed_folders=self._describe_allowed_folders(),
            protected_files=", ".join(sorted(self._options.protected_paths)),
        )
        plan = await self._planner.plan_phase(prompt_input)

        files, dropped = drop_unusable_files(plan.files, self._writer.is_allowed, self._writer.exists)
        if not files:
            raise PlanningError(f"Phase {phase.outline.id} ({phase.outline.name}) produced no usable files.")
        return PlannedPhase(order_by_dependencies(files), plan.required_packages, dropped)

    @staticmethod
    def _roadmap_summary(state: BuildState) -> str:
        lines = [f"{p.outline.id}. {p.outline.name} - {p.outline.goal} [{p.status}]" for p in state.phases]
        return "\n".join(lines)

    def _describe_allowed_folders(self) -> str:
        folders = self._options.allowed_folders
        return ", ".join(f"{folder}/" for folder in folders) if folders else "the project root"
