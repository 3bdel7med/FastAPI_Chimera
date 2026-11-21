"""Responsibility: collect honest notes about what static analysis could NOT determine."""

from __future__ import annotations

import ast

MAX_NOTES = 200


class UnresolvedNotes:
    def __init__(self) -> None:
        self._notes: list[str] = []

    def add(self, source_path: str, node: ast.AST | None, message: str) -> None:
        line = getattr(node, "lineno", 0)
        self._notes.append(f"{source_path}:{line}: {message}")

    def add_unparsable_file(self, source_path: str) -> None:
        self._notes.append(f"{source_path}: skipped (could not be parsed)")

    def to_list(self) -> list[str]:
        return sorted(set(self._notes))[:MAX_NOTES]
