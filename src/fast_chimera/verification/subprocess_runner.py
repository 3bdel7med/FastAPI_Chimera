"""Responsibility: run a command inside the project folder, safely.

The Gemini key (and any CHIMERA_* setting) is removed from the environment, so generated
code that gets executed can never read it."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fast_chimera.core.exceptions import VerificationError

_HIDDEN_PREFIXES = ("GEMINI_", "CHIMERA_")


@dataclass(frozen=True)
class ProcessResult:
    return_code: int | None  # None means the command timed out
    output: str


class SubprocessRunner:
    def __init__(self, project_root: Path, timeout_seconds: float = 180.0) -> None:
        self._root = Path(project_root)
        self._timeout = timeout_seconds

    def run(self, command: list[str]) -> ProcessResult:
        if not self._root.exists():
            raise VerificationError(f"Project directory does not exist: {self._root}")
        try:
            completed = subprocess.run(
                command,
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=self._clean_environment(),
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(None, f"Timed out after {self._timeout:.0f}s")
        except OSError as error:
            raise VerificationError(f"Could not start {command[0]}: {error}") from error

        output = f"{completed.stdout}\n{completed.stderr}".strip()
        return ProcessResult(completed.returncode, output)

    def _clean_environment(self) -> dict[str, str]:
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(_HIDDEN_PREFIXES)}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(self._root)
        return environment
