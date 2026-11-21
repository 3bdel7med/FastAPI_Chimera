"""Responsibility: run ONE phase: plan it (if not planned yet), build its files batch by batch,
verify after every batch, and run its tests at the end."""

from __future__ import annotations

from fast_chimera.engine.batch_verification import BatchVerification
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.extra_packages import remember_packages
from fast_chimera.engine.file_builder import FileBuilder
from fast_chimera.engine.options import EngineOptions
from fast_chimera.engine.phase_file_planner import PhaseFilePlanner
from fast_chimera.planning.file_plan import split_into_batches
from fast_chimera.state.models import BuildState, PhaseState
from fast_chimera.state.repository import StateRepository


class PhaseRunner:
    def __init__(
        self,
        file_planner: PhaseFilePlanner,
        file_builder: FileBuilder,
        verification: BatchVerification,
        repository: StateRepository,
        reporter: Reporter,
        options: EngineOptions,
    ) -> None:
        self._file_planner = file_planner
        self._file_builder = file_builder
        self._verification = verification
        self._repository = repository
        self._reporter = reporter
        self._options = options

    async def run(self, state: BuildState, phase: PhaseState) -> None:
        if not phase.files:
            await self._plan(state, phase)

        phase.status = "in_progress"
        batches = split_into_batches(phase.files, self._options.batch_size)
        self._reporter.phase_planned(phase, batches)

        for batch in batches:
            pending = [spec for spec in batch if spec.path not in phase.completed_files]
            for spec in pending:
                await self._file_builder.build(state, phase, spec)

            if pending and self._options.verify:
                written = [spec for spec in pending if spec.path in state.file_hashes]
                await self._verification.check_imports(state, written)

        if self._options.verify:
            await self._verification.run_phase_tests(state, phase)

    async def _plan(self, state: BuildState, phase: PhaseState) -> None:
        planned = await self._file_planner.plan(state, phase)
        for path in planned.dropped_paths:
            message = f"Ignored a planned file outside the allowed area: {path}"
            state.add_warning(message)
            self._reporter.warning(message)

        phase.files = planned.files
        phase.status = "planned"
        remember_packages(state, planned.required_packages)
        self._repository.save(state)
