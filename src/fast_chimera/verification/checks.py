"""Pattern: Command. Each check is a small object with a `run()` method returning a CheckResult.
New checks (ruff, mypy, ...) can be added without touching the existing ones."""

from __future__ import annotations

import sys
from typing import Protocol

from fast_chimera.verification.results import CheckResult
from fast_chimera.verification.subprocess_runner import SubprocessRunner

_IMPORT_SCRIPT = """
import importlib, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
try:
    from app.core.database import import_all_models
    from sqlalchemy.orm import configure_mappers
except ImportError:
    pass
else:
    import_all_models()
    configure_mappers()  # catches broken relationships / back_populates early
"""

NO_TESTS_COLLECTED = 5  # pytest's exit code when there is nothing to run: not a failure


class Check(Protocol):
    def run(self) -> CheckResult: ...


class ImportCheck:
    """Imports the given modules, then configures the SQLAlchemy mappers."""

    def __init__(self, runner: SubprocessRunner, modules: list[str], python: str = sys.executable) -> None:
        self._runner = runner
        self._modules = modules
        self._python = python

    def run(self) -> CheckResult:
        result = self._runner.run([self._python, "-c", _IMPORT_SCRIPT, *self._modules])
        return CheckResult(result.return_code == 0, result.output)


class PytestCheck:
    def __init__(self, runner: SubprocessRunner, paths: list[str] | None = None, python: str = sys.executable) -> None:
        self._runner = runner
        self._paths = paths or []
        self._python = python

    def run(self) -> CheckResult:
        command = [self._python, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider", *self._paths]
        result = self._runner.run(command)
        passed = result.return_code in (0, NO_TESTS_COLLECTED)
        return CheckResult(passed, result.output)


class PipInstallCheck:
    def __init__(self, runner: SubprocessRunner, requirements_file: str = "requirements.txt", python: str = sys.executable) -> None:
        self._runner = runner
        self._requirements_file = requirements_file
        self._python = python

    def run(self) -> CheckResult:
        result = self._runner.run([self._python, "-m", "pip", "install", "-r", self._requirements_file])
        return CheckResult(result.return_code == 0, result.output)
