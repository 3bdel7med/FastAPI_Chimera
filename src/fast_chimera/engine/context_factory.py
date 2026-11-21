from __future__ import annotations

from fast_chimera.analysis.scanner import ProjectScanner
from fast_chimera.analysis.symbol_index import format_symbol_index
from fast_chimera.generation.context import GenerationContext
from fast_chimera.state.models import BuildState, PhaseState


class ContextFactory:
    """Builds the context for one file: the request, the phase, and what the project contains right now."""

    def __init__(self, scanner: ProjectScanner) -> None:
        self._scanner = scanner

    def project_symbols(self) -> str:
        return format_symbol_index(self._scanner.scan())

    def create(self, state: BuildState, phase: PhaseState) -> GenerationContext:
        return GenerationContext(
            product_request=state.prompt,
            catalog=state.catalog,
            phase=phase.outline,
            project_symbols=self.project_symbols(),
            mode=state.mode,
        )
