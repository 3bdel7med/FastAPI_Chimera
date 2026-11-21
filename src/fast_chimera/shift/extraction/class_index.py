"""Responsibility: know every class in the project, and which ones are Pydantic schemas."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import last_name_of
from fast_chimera.shift.extraction.source_modules import SourceModule

ClassEntry = tuple[SourceModule, ast.ClassDef]


class ClassIndex:
    def __init__(self, modules: list[SourceModule]) -> None:
        self._by_name: dict[str, list[ClassEntry]] = {}
        for module in modules:
            for node in ast.walk(module.tree):
                if isinstance(node, ast.ClassDef):
                    self._by_name.setdefault(node.name, []).append((module, node))
        self._schema_names = self._find_schema_names()

    def find_base_class(self, from_module: SourceModule, base_expression: ast.expr) -> ClassEntry | None:
        """The project class a `class X(Base)` statement refers to; prefers one from the same module."""
        entries = self._by_name.get(last_name_of(base_expression) or "")
        if not entries:
            return None
        for entry in entries:
            if entry[0] is from_module:
                return entry
        return entries[0]

    def is_schema(self, class_name: str | None) -> bool:
        return class_name in self._schema_names

    def _find_schema_names(self) -> set[str]:
        """A class is a schema if it extends BaseModel, directly or through other project classes."""
        schemas: set[str] = set()
        found_new = True
        while found_new:
            found_new = False
            for name, entries in self._by_name.items():
                if name in schemas:
                    continue
                if any(self._extends_schema(class_def, schemas) for _, class_def in entries):
                    schemas.add(name)
                    found_new = True
        return schemas

    @staticmethod
    def _extends_schema(class_def: ast.ClassDef, known_schemas: set[str]) -> bool:
        base_names = {last_name_of(base) for base in class_def.bases}
        return "BaseModel" in base_names or bool(base_names & known_schemas)
