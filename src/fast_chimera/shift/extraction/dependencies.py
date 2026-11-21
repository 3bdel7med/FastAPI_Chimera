"""Responsibility: read FastAPI `Depends(...)` / `Security(...)` expressions."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import keyword_map, last_name_of, shorten

DEPENDENCY_FUNCTIONS = frozenset({"Depends", "Security"})


def is_dependency_call(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Call) and last_name_of(node.func) in DEPENDENCY_FUNCTIONS


def dependency_target(call: ast.Call) -> ast.expr | None:
    """The function/class passed to Depends(...), or None for a bare `Depends()`."""
    if call.args:
        return call.args[0]
    return keyword_map(call).get("dependency")


def dependency_names(list_expression: ast.expr | None) -> list[str]:
    """`dependencies=[Depends(a), Security(b)]` -> ["a", "b"]."""
    if not isinstance(list_expression, (ast.List, ast.Tuple)):
        return []
    names = []
    for item in list_expression.elts:
        if is_dependency_call(item):
            target = dependency_target(item)  # type: ignore[arg-type]
            if target is not None:
                names.append(shorten(ast.unparse(target)))
    return names
