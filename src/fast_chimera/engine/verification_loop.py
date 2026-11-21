"""Responsibility: run a check; when it fails, repair the file to blame and try again (bounded)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from fast_chimera.core.text import tail
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.failure_triage import triage_failure
from fast_chimera.engine.file_repairer import FileRepairer
from fast_chimera.state.models import BuildState
from fast_chimera.verification.results import CheckResult

MAX_SHOWN_OUTPUT = 600


class VerificationLoop:
    def __init__(self, project_root: Path, repairer: FileRepairer, reporter: Reporter, max_repairs: int) -> None:
        self._root = Path(project_root)
        self._repairer = repairer
        self._reporter = reporter
        self._max_repairs = max_repairs

    async def run(self, state: BuildState, label: str, check: Callable[[], CheckResult]) -> None:
        for attempt in range(self._max_repairs + 1):
            result = await asyncio.to_thread(check)  # checks run subprocesses: keep the event loop free
            if result.ok:
                self._reporter.check(label, True)
                return

            triage = triage_failure(result.output, self._root, set(state.file_hashes))

            if triage.kind == "missing_dependency":
                message = f"Missing dependency '{triage.module}': install requirements.txt / requirements-extra.txt"
                state.add_warning(message)
                self._reporter.warning(message)
                self._reporter.check(label, False, f"missing dependency '{triage.module}'")
                return

            out_of_attempts = attempt == self._max_repairs
            if triage.kind == "unknown" or out_of_attempts:
                shown = tail(result.output, MAX_SHOWN_OUTPUT)
                state.add_warning(f"{label} failing: {shown}")
                self._reporter.check(label, False, shown)
                return

            self._reporter.info(f"{label} failed; repairing {triage.file} (attempt {attempt + 1})")
            await self._repairer.repair(state, triage.file or "", result.output)
