"""Responsibility: build ONE file from start to finish (decide, generate, write, register, record)."""

from __future__ import annotations

from fast_chimera.core.exceptions import FastChimeraError, FileConflictError, FileGenerationError
from fast_chimera.engine.context_factory import ContextFactory
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.overwrite_policy import OverwritePolicy, WriteDecision
from fast_chimera.engine.router_registrar import RouterRegistrar
from fast_chimera.generation.generator import FileGenerator
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.planning.schemas import FileSpec
from fast_chimera.state.models import BuildState, PhaseState
from fast_chimera.state.repository import StateRepository


class FileBuilder:
    def __init__(
        self,
        generator: FileGenerator,
        writer: SafeWriter,
        contexts: ContextFactory,
        policy: OverwritePolicy,
        registrar: RouterRegistrar,
        repository: StateRepository,
        reporter: Reporter,
    ) -> None:
        self._generator = generator
        self._writer = writer
        self._contexts = contexts
        self._policy = policy
        self._registrar = registrar
        self._repository = repository
        self._reporter = reporter

    async def build(self, state: BuildState, phase: PhaseState, spec: FileSpec) -> None:
        self._reporter.file_started(spec)
        path = spec.path

        file_exists = self._writer.exists(path)
        if spec.action == "MODIFY" and not file_exists:
            spec.action = "CREATE"  # nothing to modify yet

        decision = self._policy.decide(file_exists=file_exists, written_by_us=path in state.file_hashes, action=spec.action)
        if decision is WriteDecision.SKIP_USER_FILE:
            self._skip(state, phase, spec, "exists and was not created by FastChimera (use --force to replace it)")
            return

        context = self._contexts.create(state, phase)
        current_code = self._writer.read(path) if file_exists else None
        try:
            code = await self._generator.generate(spec, context, current_code)
            overwrite = decision is WriteDecision.OVERWRITE
            state.file_hashes[path] = self._writer.write(path, code, overwrite=overwrite)
        except FileConflictError as error:
            self._skip(state, phase, spec, str(error))
            return
        except FastChimeraError as error:
            raise FileGenerationError(f"{path}: {error}") from error

        warning = self._registrar.register(spec)
        if warning:
            state.add_warning(warning)
            self._reporter.warning(warning)

        phase.completed_files.append(path)
        self._repository.save(state)
        self._reporter.file_done(spec)

    def _skip(self, state: BuildState, phase: PhaseState, spec: FileSpec, reason: str) -> None:
        state.add_warning(f"Skipped {spec.path}: {reason}")
        self._reporter.warning(f"Skipped {spec.path}: {reason}")
        self._reporter.file_skipped(spec, reason)
        phase.completed_files.append(spec.path)  # counted as handled, so a resume does not retry it
        self._repository.save(state)
