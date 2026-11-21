"""Responsibility: find the Python files of a project, skipping virtualenvs, caches and the like.
Shared by the scanner and by the `shift` extractor."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

ALWAYS_IGNORED_FOLDERS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "site-packages",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".fast-chimera",
    }
)


def is_ignored_folder(name: str, extra_ignored: Iterable[str] = ()) -> bool:
    return name in ALWAYS_IGNORED_FOLDERS or name in set(extra_ignored) or name.endswith(".egg-info")


def find_python_files(root: Path, extra_ignored_folders: Iterable[str] = ()) -> Iterator[tuple[Path, Path]]:
    """Yields (absolute path, path relative to root), sorted, skipping ignored folders."""
    extra = tuple(extra_ignored_folders)
    for absolute in sorted(root.rglob("*.py")):
        relative = absolute.relative_to(root)
        folders = relative.parts[:-1]
        if any(is_ignored_folder(folder, extra) for folder in folders):
            continue
        yield absolute, relative
