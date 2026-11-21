"""Pattern: Composition Root. The ONE place where concrete classes are created and wired together.

Everywhere else, classes receive their collaborators in the constructor. To swap a part (another
LLM, another verifier, another writer) change this file only."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.analysis.scanner import ProjectScanner
from fast_chimera.core.interfaces import LlmClient
from fast_chimera.engine.batch_verification import BatchVerification
from fast_chimera.engine.build_engine import BuildEngine
from fast_chimera.engine.context_factory import ContextFactory
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.file_builder import FileBuilder
from fast_chimera.engine.file_repairer import FileRepairer
from fast_chimera.engine.finalizer import Finalizer
from fast_chimera.engine.options import EngineOptions
from fast_chimera.engine.overwrite_policy import OverwritePolicy
from fast_chimera.engine.phase_file_planner import PhaseFilePlanner
from fast_chimera.engine.phase_runner import PhaseRunner
from fast_chimera.engine.router_registrar import RouterRegistrar
from fast_chimera.engine.verification_loop import VerificationLoop
from fast_chimera.generation.backup import BackupService
from fast_chimera.generation.dependency_sources import DependencySourceReader
from fast_chimera.generation.generator import FileGenerator
from fast_chimera.generation.path_policy import PathPolicy
from fast_chimera.generation.prompt_builder import FilePromptBuilder
from fast_chimera.generation.validators import ValidatorChain
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.planning.planner import Planner
from fast_chimera.state.repository import JsonStateRepository
from fast_chimera.verification.verifier import ProjectVerifier


def create_build_engine(
    project_root: Path,
    llm: LlmClient,
    options: EngineOptions | None = None,
    reporter: Reporter | None = None,
) -> BuildEngine:
    root = Path(project_root).resolve()
    options = options or EngineOptions()
    reporter = reporter or Reporter()

    repository = JsonStateRepository(root)
    scanner = ProjectScanner(root)
    contexts = ContextFactory(scanner)
    verifier = ProjectVerifier(root)

    writer = SafeWriter(
        PathPolicy(root, protected_paths=options.protected_paths, allowed_folders=options.allowed_folders),
        BackupService(root / ".fast-chimera" / "backups"),
    )
    generator = FileGenerator(
        llm,
        FilePromptBuilder(DependencySourceReader(root)),
        ValidatorChain(),
        options.max_repair_attempts,
    )

    repairer = FileRepairer(generator, writer, contexts, repository)
    loop = VerificationLoop(root, repairer, reporter, options.max_repair_attempts)
    verification = BatchVerification(verifier, loop, root, options.main_file)

    file_builder = FileBuilder(
        generator,
        writer,
        contexts,
        OverwritePolicy(options.force),
        RouterRegistrar(writer, options.main_file),
        repository,
        reporter,
    )
    file_planner = PhaseFilePlanner(Planner(llm), writer, contexts, options)
    phase_runner = PhaseRunner(file_planner, file_builder, verification, repository, reporter, options)
    finalizer = Finalizer(root, verifier, repository, reporter, options.verify)

    return BuildEngine(phase_runner, finalizer, repository, reporter)
