"""Responsibility: turn a column type expression into a short, framework-neutral name."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import last_name_of

_ALIASES = {
    "integer": "integer",
    "int": "integer",
    "biginteger": "bigint",
    "smallinteger": "smallint",
    "string": "string",
    "str": "string",
    "varchar": "string",
    "unicode": "string",
    "text": "text",
    "unicodetext": "text",
    "boolean": "boolean",
    "bool": "boolean",
    "datetime": "datetime",
    "timestamp": "datetime",
    "date": "date",
    "time": "time",
    "interval": "interval",
    "timedelta": "interval",
    "numeric": "decimal",
    "decimal": "decimal",
    "float": "float",
    "json": "json",
    "jsonb": "json",
    "dict": "json",
    "list": "json",
    "largebinary": "binary",
    "bytes": "binary",
    "binary": "binary",
    "uuid": "uuid",
    "enum": "enum",
}
_TYPES_WITH_PARAMETERS = ("string", "decimal", "float", "enum")


def normalize_type_name(expression: ast.expr | None) -> str:
    """`String(120)` -> "string(120)", `Numeric(12, 2)` -> "decimal(12,2)", `int` -> "integer"."""
    if expression is None:
        return "unknown"

    type_node = expression.func if isinstance(expression, ast.Call) else expression
    raw_name = last_name_of(type_node)
    if not raw_name:
        return "unknown"

    name = _ALIASES.get(raw_name.lower(), raw_name.lower())
    if isinstance(expression, ast.Call) and name in _TYPES_WITH_PARAMETERS:
        constants = [str(arg.value) for arg in expression.args if isinstance(arg, ast.Constant)]
        if constants:
            name += f"({','.join(constants)})"
    return name
