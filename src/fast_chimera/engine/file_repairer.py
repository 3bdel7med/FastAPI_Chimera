"""Responsibility: fix one generated file, using the error output as the problem description."""

from __future__ import annotations

from fast_chimera.core.text import tail
from fast_chimera.engine.context_factory import ContextFactory
from fast_chimera.generation.generator import FileGenerator
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.planning.schemas import FileSpec
from fast_chimera.state.models import BuildState, PhaseState
from fast_chimera.state.repository import StateRepository

MAX_ERROR_CHARS = 3500


class FileRepairer:
    def __init__(
        self,
        generator: FileGenerator,
        writer: SafeWriter,
        contexts: ContextFactory,
        repository: StateRepository,
    ) -> None:
        self._generator = generator
        self._writer = writer
        self._contexts = contexts
        self._repository = repository

    async def repair(self, state: BuildState, relative_path: str, error_output: str) -> None:
        phase = self._phase_owning(state, relative_path)
        spec = self._spec_for(phase, relative_path)
        current_code = self._writer.read(relative_path) or ""

        context = self._contexts.create(state, phase)
        fixed_code = await self._generator.repair(spec, context, current_code, tail(error_output, MAX_ERROR_CHARS))

        state.file_hashes[relative_path] = self._writer.write(relative_path, fixed_code, overwrite=True)
        self._repository.save(state)

    @staticmethod
    def _phase_owning(state: BuildState, relative_path: str) -> PhaseState:
        for phase in state.phases:
            if any(spec.path == relative_path for spec in phase.files):
                return phase
        return state.phases[-1]

    @staticmethod
    def _spec_for(phase: PhaseState, relative_path: str) -> FileSpec:
        for spec in phase.files:
            if spec.path == relative_path:
                return spec
        return FileSpec(path=relative_path, purpose="(unknown)")
