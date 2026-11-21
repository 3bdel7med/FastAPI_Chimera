"""Responsibility: load the project's Python files as parsed modules."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from fast_chimera.analysis.file_discovery import find_python_files
from fast_chimera.core.paths import path_to_module
from fast_chimera.shift.extraction.imports import ImportMap, collect_imports
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes

# Folders that never describe the application itself.
NON_APPLICATION_FOLDERS = ("tests", "test", "alembic", "migrations")


@dataclass
class SourceModule:
    path: str  # relative file path, e.g. app/routers/vendors.py
    name: str  # dotted module name, e.g. app.routers.vendors
    is_package: bool
    tree: ast.Module
    imports: ImportMap = field(default_factory=dict)


def load_source_modules(root: Path, notes: UnresolvedNotes) -> list[SourceModule]:
    modules: list[SourceModule] = []
    for absolute, relative in find_python_files(root, NON_APPLICATION_FOLDERS):
        if relative.name.startswith("test_") or relative.name == "conftest.py":
            continue
        try:
            tree = ast.parse(absolute.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            notes.add_unparsable_file(relative.as_posix())
            continue

        name = _module_name(root, relative)
        is_package = relative.name == "__init__.py"
        modules.append(SourceModule(relative.as_posix(), name, is_package, tree, collect_imports(name, is_package, tree)))
    return modules


def _module_name(root: Path, relative: Path) -> str:
    """Handles the `src/` layout: src/pkg/x.py is imported as pkg.x."""
    parts = relative.parts
    uses_src_layout = parts[0] == "src" and len(parts) > 1 and not (root / "src" / "__init__.py").exists()
    if uses_src_layout:
        parts = parts[1:]
    return path_to_module("/".join(parts))
