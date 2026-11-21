"""Responsibility: turn one column declaration into a ColumnInfo.

Understands: SQLAlchemy 2.0 `mapped_column`, classic `Column(...)`, annotation-only `Mapped[...]`,
and SQLModel `Field(...)`."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fast_chimera.shift.extraction.annotations import Annotation
from fast_chimera.shift.extraction.ast_utils import bool_value, keyword_map, last_name_of, string_value
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.type_names import normalize_type_name
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import ColumnInfo

COLUMN_FUNCTIONS = frozenset({"mapped_column", "Column", "Field"})


@dataclass
class _PositionalArguments:
    database_name: str
    type_expression: ast.expr | None = None
    foreign_key: str | None = None
    on_delete: str | None = None


class ColumnParser:
    def __init__(self, notes: UnresolvedNotes) -> None:
        self._notes = notes

    def parse(
        self,
        module: SourceModule,
        attribute_name: str,
        call: ast.Call | None,
        annotation: Annotation | None,
    ) -> ColumnInfo:
        call = self._use_sqlmodel_inner_column(call)
        keywords = keyword_map(call) if call else {}
        arguments = self._read_positional_arguments(call, attribute_name)

        flags = {key: self._read_flag(module, attribute_name, keywords, key) for key in ("primary_key", "nullable", "unique", "index")}
        primary_key = bool(flags["primary_key"])

        return ColumnInfo(
            name=string_value(keywords.get("name")) or arguments.database_name,
            type=self._decide_type(arguments.type_expression, annotation),
            nullable=self._decide_nullable(flags["nullable"], primary_key, annotation),
            primary_key=primary_key,
            unique=bool(flags["unique"]),
            index=bool(flags["index"]),
            foreign_key=arguments.foreign_key or string_value(keywords.get("foreign_key")),
            on_delete=arguments.on_delete,
        )

    @staticmethod
    def _use_sqlmodel_inner_column(call: ast.Call | None) -> ast.Call | None:
        """SQLModel's `Field(sa_column=Column(...))` hides the real column inside."""
        if call is not None and last_name_of(call.func) == "Field":
            inner = keyword_map(call).get("sa_column")
            if isinstance(inner, ast.Call):
                return inner
        return call

    @staticmethod
    def _read_positional_arguments(call: ast.Call | None, attribute_name: str) -> _PositionalArguments:
        result = _PositionalArguments(database_name=attribute_name)
        if call is None:
            return result

        for position, argument in enumerate(call.args):
            text = string_value(argument)
            if position == 0 and text is not None:
                result.database_name = text  # Column("db_name", Integer)
            elif isinstance(argument, ast.Call) and last_name_of(argument.func) == "ForeignKey":
                result.foreign_key = string_value(argument.args[0]) if argument.args else None
                result.on_delete = string_value(keyword_map(argument).get("ondelete"))
            elif result.type_expression is None and isinstance(argument, (ast.Name, ast.Attribute, ast.Call, ast.Subscript)):
                result.type_expression = argument
        return result

    def _read_flag(self, module: SourceModule, attribute: str, keywords: dict[str, ast.expr], key: str) -> bool | None:
        if key not in keywords:
            return None
        value = bool_value(keywords[key])
        if value is None:
            self._notes.add(module.path, keywords[key], f"column {attribute}: '{key}' is not a constant")
        return value

    @staticmethod
    def _decide_nullable(explicit: bool | None, primary_key: bool, annotation: Annotation | None) -> bool:
        if explicit is not None:
            return explicit
        if primary_key:
            return False
        if annotation is not None:
            return annotation.optional  # SQLAlchemy 2.0 infers nullability from Optional[...]
        return True  # classic Column() default

    @staticmethod
    def _decide_type(type_expression: ast.expr | None, annotation: Annotation | None) -> str:
        if type_expression is not None:
            return normalize_type_name(type_expression)
        if annotation is not None and annotation.core is not None:
            return "json" if annotation.is_collection else normalize_type_name(annotation.core)
        return "unknown"
