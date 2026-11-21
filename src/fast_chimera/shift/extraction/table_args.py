"""Responsibility: read `__table_args__` (composite unique constraints and indexes)."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import bool_value, keyword_map, last_name_of, string_value
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import IndexInfo


def parse_table_args(
    module: SourceModule,
    value: ast.expr | None,
    unique_constraints: list[list[str]],
    indexes: list[IndexInfo],
    notes: UnresolvedNotes,
) -> None:
    items = value.elts if isinstance(value, (ast.Tuple, ast.List)) else [value]
    for item in items:
        if not isinstance(item, ast.Call):
            continue

        constructor = last_name_of(item.func)
        string_arguments = [text for text in (string_value(arg) for arg in item.args) if text]

        if constructor == "UniqueConstraint":
            unique_constraints.append(string_arguments)
        elif constructor == "Index" and string_arguments:
            is_unique = bool(bool_value(keyword_map(item).get("unique")))
            indexes.append(IndexInfo(name=string_arguments[0], columns=string_arguments[1:], unique=is_unique))
        elif constructor == "ForeignKeyConstraint":
            notes.add(module.path, item, "composite ForeignKeyConstraint was not captured")
