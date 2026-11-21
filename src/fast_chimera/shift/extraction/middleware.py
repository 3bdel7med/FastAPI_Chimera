"""Responsibility: list the GLOBAL middleware: things that apply to every request."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import keyword_map, last_name_of
from fast_chimera.shift.extraction.router_graph import RouterGraph, RouterReferences
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.schema import MiddlewareInfo


def collect_global_middleware(modules: list[SourceModule], graph: RouterGraph, references: RouterReferences) -> list[MiddlewareInfo]:
    found: list[MiddlewareInfo] = []

    # 1) Declared in the FastAPI(...) constructor: `dependencies=[...]` and `middleware=[...]`
    for router_node in graph.nodes.values():
        if router_node.kind == "app":
            found += [MiddlewareInfo(name=name, kind="dependency") for name in router_node.dependencies]
            found += router_node.constructor_middleware

    # 2) `app.add_middleware(X, ...)` and `@app.middleware("http")`
    for module in modules:
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and _is_method_call(node, "add_middleware") and node.args:
                name = last_name_of(node.args[0]) or "?"
                found.append(MiddlewareInfo(name=name, kind="middleware", options=sorted(keyword_map(node))))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found += _http_middleware_decorators(module, node, references)
    return found


def _is_method_call(call: ast.Call, method: str) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == method


def _http_middleware_decorators(
    module: SourceModule, function: ast.FunctionDef | ast.AsyncFunctionDef, references: RouterReferences
) -> list[MiddlewareInfo]:
    found = []
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not _is_method_call(decorator, "middleware"):
            continue
        assert isinstance(decorator.func, ast.Attribute)
        if references.key_for(module, decorator.func.value):
            found.append(MiddlewareInfo(name=function.name, kind="http"))
    return found
