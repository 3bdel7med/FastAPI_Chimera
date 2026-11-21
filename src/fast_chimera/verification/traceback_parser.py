"""Responsibility: read tracebacks and pytest output to find WHAT failed and WHICH of our files is to blame."""

from __future__ import annotations

import re
from pathlib import Path

_MISSING_MODULE = re.compile(r"No module named '([\w.\-]+)'")
# Either `File "/abs/path.py", line 3` (tracebacks) or `app/x.py:12:` (pytest).
_MENTIONED_FILE = re.compile(r'File "([^"]+)", line \d+|^([\w./\\-]+\.py):\d+', re.MULTILINE)


def find_missing_module(output: str) -> str | None:
    match = _MISSING_MODULE.search(output)
    return match.group(1) if match else None


def locate_failing_file(output: str, project_root: Path, generated_files: set[str]) -> str | None:
    """The LAST file in the output that FastChimera generated: usually where the error was raised."""
    root = Path(project_root).resolve()
    culprit: str | None = None

    for match in _MENTIONED_FILE.finditer(output):
        mentioned = Path(match.group(1) or match.group(2))
        if not mentioned.is_absolute():
            mentioned = root / mentioned
        try:
            relative = mentioned.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            continue  # a file outside the project (e.g. site-packages)
        if relative in generated_files:
            culprit = relative
    return culprit
