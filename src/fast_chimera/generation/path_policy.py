"""Responsibility: decide whether a generated file path is acceptable, and where it lives on disk."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from fast_chimera.core.exceptions import UnsafePathError
from fast_chimera.core.paths import normalize_relative_path


class PathPolicy:
    def __init__(
        self,
        root: Path,
        *,
        protected_paths: Iterable[str] = (),
        allowed_folders: tuple[str, ...] | None = ("app", "tests"),
    ) -> None:
        self.root = Path(root).resolve()
        self._protected = frozenset(protected_paths)
        self._allowed_folders = allowed_folders

    def resolve(self, relative_path: str) -> Path:
        """The absolute path for a file we may write, or UnsafePathError."""
        relative = normalize_relative_path(relative_path)

        if relative in self._protected:
            raise UnsafePathError(f"{relative} is a protected scaffold file")

        top_folder = PurePosixPath(relative).parts[0]
        if self._allowed_folders and top_folder not in self._allowed_folders:
            raise UnsafePathError(f"{relative} is outside the allowed folders {self._allowed_folders}")

        absolute = (self.root / relative).resolve()  # resolve() follows symlinks
        if not absolute.is_relative_to(self.root):
            raise UnsafePathError(f"{relative} escapes the project directory")
        return absolute

    def is_allowed(self, relative_path: str) -> bool:
        try:
            self.resolve(relative_path)
        except UnsafePathError:
            return False
        return True
