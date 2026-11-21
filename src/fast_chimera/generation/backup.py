"""Responsibility: keep a copy of a file before it is replaced."""

from __future__ import annotations

import time
from pathlib import Path


class BackupService:
    def __init__(self, backup_root: Path) -> None:
        # One folder per run, e.g. .fast-chimera/backups/20260101-120000/
        self.run_folder = Path(backup_root) / time.strftime("%Y%m%d-%H%M%S")

    def save(self, file_path: Path, relative_path: str) -> Path:
        destination = self.run_folder / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_path.read_bytes())
        return destination
