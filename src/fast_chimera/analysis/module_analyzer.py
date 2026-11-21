"""Responsibility: read ONE module's source and describe its classes, functions, routers and routes."""

from __future__ import annotations

import ast

from fast_chimera.analysis.ast_describers import (
    class_field_names,
    function_signature,
    router_declaration,
)
from fast_chimera.analysis.class_kinds import classify_class
from fast_chimera.analysis.models import ClassInfo, ModuleInfo, RouteInfo
from fast_chimera.core.paths import path_to_module

HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "options", "head"})


def analyze_source(code: str, relative_path: str) -> ModuleInfo:
    """Raises SyntaxError when the code cannot be parsed (the scanner skips such files)."""
    tree = ast.parse(code)
    info = ModuleInfo(module=path_to_module(relative_path), path=relative_path)

    for statement in tree.body:
        _read_top_level_statement(statement, info)
    info.routes = _find_routes(tree, info.module)
    return info


def find_router_variables(code: str) -> list[str]:
    """Names assigned `X = APIRouter(...)` at module level. Empty when the code has a syntax error."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    names = []
    for statement in tree.body:
        declaration = router_declaration(statement)
        if declaration:
            names.append(declaration[0])
    return names


def _read_top_level_statement(statement: ast.stmt, info: ModuleInfo) -> None:
    if isinstance(statement, ast.ClassDef):
        base_names = [ast.unparse(base) for base in statement.bases]
        info.classes.append(ClassInfo(statement.name, base_names, class_field_names(statement), classify_class(base_names), info.module))
    elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        info.functions.append(function_signature(statement))
    else:
        declaration = router_declaration(statement)
        if declaration:
            name, prefix = declaration
            info.routers.append(f"{name} ({prefix})" if prefix else name)


def _find_routes(tree: ast.Module, module_name: str) -> list[RouteInfo]:
    routes: list[RouteInfo] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            route = _route_from_decorator(decorator, node.name, module_name)
            if route:
                routes.append(route)
    return routes


def _route_from_decorator(decorator: ast.expr, function_name: str, module_name: str) -> RouteInfo | None:
    """`@router.get("/x")` becomes a RouteInfo; any other decorator becomes None."""
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    if decorator.func.attr not in HTTP_METHODS:
        return None
    path = ast.unparse(decorator.args[0]).strip("'\"") if decorator.args else "?"
    return RouteInfo(
        method=decorator.func.attr.upper(),
        path=path,
        function=function_name,
        router=ast.unparse(decorator.func.value),
        module=module_name,
    )
