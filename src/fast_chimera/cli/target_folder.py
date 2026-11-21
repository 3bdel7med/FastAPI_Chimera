from __future__ import annotations

from pathlib import Path

from fast_chimera.core.exceptions import FastChimeraError
from fast_chimera.state.repository import JsonStateRepository

_IGNORED_ENTRIES = {".env", ".git"}


def ensure_target_is_free(target: Path) -> None:
    """A new project may only be created in a folder that does not exist yet or is (almost) empty."""
    if not target.exists():
        return
    has_content = any(entry.name not in _IGNORED_ENTRIES for entry in target.iterdir())
    if not has_content:
        return

    hint = " Use `fast-chimera resume` to continue it." if JsonStateRepository(target).exists() else ""
    raise FastChimeraError(f"{target} is not empty.{hint} Pick another --output directory.")
