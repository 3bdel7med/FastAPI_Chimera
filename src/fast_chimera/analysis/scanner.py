"""Responsibility: scan a project folder and describe it (read-only, nothing is executed)."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.analysis.file_discovery import find_python_files
from fast_chimera.analysis.models import ModuleInfo, ProjectSummary
from fast_chimera.analysis.module_analyzer import analyze_source
from fast_chimera.core.exceptions import AstParsingError


class ProjectScanner:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def scan(self) -> ProjectSummary:
        if not self.project_root.exists():
            raise AstParsingError(f"Project directory does not exist: {self.project_root}")

        modules: list[ModuleInfo] = []
        skipped: list[str] = []
        for absolute, relative in find_python_files(self.project_root):
            try:
                modules.append(analyze_source(absolute.read_text(encoding="utf-8"), relative.as_posix()))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                skipped.append(relative.as_posix())  # one broken file must not stop the whole scan
        return ProjectSummary(root=str(self.project_root), modules=modules, skipped=skipped)
