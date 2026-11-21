"""Responsibility: the wrap-up after the last phase."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fast_chimera.core.text import tail
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.extra_packages import REVIEW_WARNING, write_requirements_file
from fast_chimera.planning.catalog_formatting import to_markdown
from fast_chimera.state.models import BuildState
from fast_chimera.state.repository import StateRepository
from fast_chimera.verification.verifier import Verifier

MAX_SHOWN_OUTPUT = 800


class Finalizer:
    def __init__(
        self,
        project_root: Path,
        verifier: Verifier,
        repository: StateRepository,
        reporter: Reporter,
        verify: bool,
    ) -> None:
        self._root = Path(project_root)
        self._verifier = verifier
        self._repository = repository
        self._reporter = reporter
        self._verify = verify

    async def finish(self, state: BuildState) -> None:
        if write_requirements_file(self._root, state):
            state.add_warning(REVIEW_WARNING)
            self._reporter.warning(REVIEW_WARNING)

        if state.mode == "build":
            (self._root / "FEATURES.md").write_text(to_markdown(state.catalog), encoding="utf-8")

        if self._verify:
            result = await asyncio.to_thread(self._verifier.run_pytest)
            detail = "" if result.ok else tail(result.output, MAX_SHOWN_OUTPUT)
            self._reporter.check("final test run", result.ok, detail)

        self._repository.save(state)
