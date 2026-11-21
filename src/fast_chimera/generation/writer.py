"""Responsibility: the ONLY place that writes generated files to disk.

It guarantees that files stay inside the project, avoid protected paths, are never silently
overwritten, and are backed up when they are replaced. The rules themselves live in
`PathPolicy` and `BackupService`; this class puts them together."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.core.exceptions import FileConflictError
from fast_chimera.core.paths import normalize_relative_path
from fast_chimera.core.text import sha256_text
from fast_chimera.generation.backup import BackupService
from fast_chimera.generation.package_folders import ensure_package_folders
from fast_chimera.generation.path_policy import PathPolicy


class SafeWriter:
    def __init__(self, policy: PathPolicy, backups: BackupService) -> None:
        self._policy = policy
        self._backups = backups

    @property
    def root(self) -> Path:
        return self._policy.root

    def is_allowed(self, relative_path: str) -> bool:
        return self._policy.is_allowed(relative_path)

    def exists(self, relative_path: str) -> bool:
        return (self._policy.root / normalize_relative_path(relative_path)).is_file()

    def read(self, relative_path: str) -> str | None:
        file_path = self._policy.root / normalize_relative_path(relative_path)
        return file_path.read_text(encoding="utf-8") if file_path.is_file() else None

    def write(self, relative_path: str, content: str, *, overwrite: bool) -> str:
        """Write the file and return the sha256 of what was written."""
        target = self._policy.resolve(relative_path)

        if target.exists():
            if not overwrite:
                raise FileConflictError(f"{relative_path} already exists and was not created by FastChimera")
            self._backups.save(target, relative_path)

        ensure_package_folders(target.parent, self._policy.root)
        text = content.rstrip() + "\n"
        target.write_text(text, encoding="utf-8")
        return sha256_text(text)
