"""Responsibility: tiny, well-named helpers for reading AST nodes. No FastAPI knowledge in here."""

from __future__ import annotations

import ast


def last_name_of(node: ast.AST | None) -> str | None:
    """`a.b.Foo` -> "Foo", `Foo[int]` -> "Foo", `"pkg.Foo"` -> "Foo", `Foo(...)` -> "Foo"."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split(".")[-1].strip() or None
    if isinstance(node, ast.Subscript):
        return last_name_of(node.value)
    if isinstance(node, ast.Call):
        return last_name_of(node.func)
    return None


def string_value(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def bool_value(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def is_none_constant(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def string_list(node: ast.AST | None) -> list[str]:
    """["a", "b"] -> ["a", "b"]. Non-constant items are ignored."""
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return []
    strings = [string_value(item) for item in node.elts]
    return [text for text in strings if text is not None]


def shorten(text: str, limit: int = 80) -> str:
    text = text.replace("'", "").replace('"', "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def keyword_map(call: ast.Call) -> dict[str, ast.expr]:
    return {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}


def assignment_parts(statement: ast.stmt) -> tuple[str | None, ast.expr | None, ast.expr | None]:
    """For `x = value` or `x: Annotation = value` return (name, value, annotation); else (None, None, None)."""
    if isinstance(statement, ast.Assign):
        if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            return statement.targets[0].id, statement.value, None
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id, statement.value, statement.annotation
    return None, None, None
