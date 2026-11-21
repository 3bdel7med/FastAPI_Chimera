"""Responsibility: describe single AST nodes as short strings. Pure functions, easy to test."""

from __future__ import annotations

import ast

MAX_LISTED_FIELDS = 30


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    keyword = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{keyword} {node.name}({ast.unparse(node.args)}){returns}"


def class_field_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names.append(statement.target.id)
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("__"):
                    names.append(target.id)
    return names[:MAX_LISTED_FIELDS]


def router_declaration(statement: ast.stmt) -> tuple[str, str] | None:
    """For `router = APIRouter(prefix="/users")` return ("router", "prefix='/users'"), else None."""
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None
    value = statement.value
    if not isinstance(value, ast.Call):
        return None
    if ast.unparse(value.func).split(".")[-1] != "APIRouter":
        return None

    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    names = [target.id for target in targets if isinstance(target, ast.Name)]
    if not names:
        return None

    prefix = ""
    for keyword in value.keywords:
        if keyword.arg == "prefix":
            prefix = f"prefix={ast.unparse(keyword.value)}"
    return names[0], prefix
