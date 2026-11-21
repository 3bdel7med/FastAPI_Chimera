"""Responsibility: create missing folders, each with an `__init__.py`, so new imports just work."""

from __future__ import annotations

from pathlib import Path


def ensure_package_folders(folder: Path, root: Path) -> None:
    missing: list[Path] = []
    current = folder
    while current != root and not current.exists():
        missing.append(current)
        current = current.parent

    folder.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):  # outermost first
        (created / "__init__.py").touch()
