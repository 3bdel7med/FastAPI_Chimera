"""Responsibility: the two verifications the engine runs: imports after a batch, tests after a phase."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.core.paths import path_to_module
from fast_chimera.engine.verification_loop import VerificationLoop
from fast_chimera.planning.schemas import FileSpec
from fast_chimera.state.models import BuildState, PhaseState
from fast_chimera.verification.verifier import Verifier


class BatchVerification:
    def __init__(self, verifier: Verifier, loop: VerificationLoop, project_root: Path, main_file: str | None) -> None:
        self._verifier = verifier
        self._loop = loop
        self._root = Path(project_root)
        self._main_file = main_file

    async def check_imports(self, state: BuildState, written_specs: list[FileSpec]) -> None:
        modules = [path_to_module(spec.path) for spec in written_specs if spec.kind != "test"]
        if not modules:
            return
        if self._main_file and (self._root / self._main_file).exists():
            modules.append(path_to_module(self._main_file))
        await self._loop.run(state, "import check", lambda: self._verifier.check_imports(modules))

    async def run_phase_tests(self, state: BuildState, phase: PhaseState) -> None:
        test_files = [path for path in phase.completed_files if path.startswith("tests/") and path in state.file_hashes]
        if not test_files:
            return
        label = f"tests (phase {phase.outline.id})"
        await self._loop.run(state, label, lambda: self._verifier.run_pytest(test_files))
