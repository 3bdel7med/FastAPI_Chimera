"""Pattern: Facade over the individual checks, so the engine depends on one small interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fast_chimera.verification.checks import ImportCheck, PipInstallCheck, PytestCheck
from fast_chimera.verification.results import CheckResult
from fast_chimera.verification.subprocess_runner import SubprocessRunner


class Verifier(Protocol):
    """What the engine needs from verification (Interface Segregation)."""

    def check_imports(self, modules: list[str]) -> CheckResult: ...
    def run_pytest(self, paths: list[str] | None = None) -> CheckResult: ...
    def install_requirements(self) -> CheckResult: ...


class ProjectVerifier:
    def __init__(self, project_root: Path, timeout_seconds: float = 180.0) -> None:
        self._runner = SubprocessRunner(project_root, timeout_seconds)

    def check_imports(self, modules: list[str]) -> CheckResult:
        return ImportCheck(self._runner, modules).run()

    def run_pytest(self, paths: list[str] | None = None) -> CheckResult:
        return PytestCheck(self._runner, paths).run()

    def install_requirements(self) -> CheckResult:
        return PipInstallCheck(self._runner).run()
