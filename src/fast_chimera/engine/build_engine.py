"""Pattern: Facade. `BuildEngine.run(state)` is the one call the CLI needs.

Everything else (planning a phase, building a file, verifying, repairing) is delegated to small
collaborators that are injected, not created here (Dependency Inversion)."""

from __future__ import annotations

from fast_chimera.engine.events import Reporter
from fast_chimera.engine.finalizer import Finalizer
from fast_chimera.engine.phase_runner import PhaseRunner
from fast_chimera.state.models import BuildState
from fast_chimera.state.repository import StateRepository


class BuildEngine:
    def __init__(
        self,
        phase_runner: PhaseRunner,
        finalizer: Finalizer,
        repository: StateRepository,
        reporter: Reporter,
    ) -> None:
        self._phase_runner = phase_runner
        self._finalizer = finalizer
        self._repository = repository
        self._reporter = reporter

    async def run(self, state: BuildState) -> BuildState:
        total = len(state.phases)
        for index, phase in enumerate(state.phases, start=1):
            if phase.status == "done":
                continue  # finished in an earlier run

            self._reporter.phase_started(index, total, phase)
            try:
                await self._phase_runner.run(state, phase)
            except Exception:
                phase.status = "failed"
                self._repository.save(state)
                raise
            phase.status = "done"
            self._repository.save(state)

        await self._finalizer.finish(state)
        return state
