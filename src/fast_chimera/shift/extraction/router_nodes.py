"""Responsibility: find the `FastAPI(...)` and `APIRouter(...)` objects a project declares."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

from fast_chimera.shift.extraction.ast_utils import assignment_parts, keyword_map, last_name_of, string_list, string_value
from fast_chimera.shift.extraction.dependencies import dependency_names
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import MiddlewareInfo

# (module name, variable name), e.g. ("app.routers.vendors", "router")
RouterKey = tuple[str, str]


@dataclass
class RouterNode:
    kind: Literal["app", "router"]
    prefix: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    constructor_middleware: list[MiddlewareInfo] = field(default_factory=list)


def find_router_nodes(modules: list[SourceModule], notes: UnresolvedNotes) -> dict[RouterKey, RouterNode]:
    nodes: dict[RouterKey, RouterNode] = {}
    for module in modules:
        for statement in ast.walk(module.tree):
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            variable, value, _ = assignment_parts(statement)
            if not variable or not isinstance(value, ast.Call):
                continue

            constructor = last_name_of(value.func)
            if constructor == "FastAPI":
                nodes[(module.name, variable)] = _build_node("app", module, value, notes)
            elif constructor == "APIRouter":
                nodes[(module.name, variable)] = _build_node("router", module, value, notes)
    return nodes


def read_prefix(module: SourceModule, call: ast.Call, notes: UnresolvedNotes) -> str:
    expression = keyword_map(call).get("prefix")
    if expression is None:
        return ""
    prefix = string_value(expression)
    if prefix is None:
        notes.add(module.path, call, "router prefix is not a constant string")
        return ""
    return prefix


def _build_node(kind: Literal["app", "router"], module: SourceModule, call: ast.Call, notes: UnresolvedNotes) -> RouterNode:
    keywords = keyword_map(call)
    node = RouterNode(
        kind=kind,
        prefix=read_prefix(module, call, notes),
        tags=string_list(keywords.get("tags")),
        dependencies=dependency_names(keywords.get("dependencies")),
    )
    if kind == "app":
        node.constructor_middleware = _middleware_from_constructor(keywords.get("middleware"))
    return node


def _middleware_from_constructor(expression: ast.expr | None) -> list[MiddlewareInfo]:
    """`FastAPI(middleware=[Middleware(CORSMiddleware, allow_origins=[...])])`: names only."""
    if not isinstance(expression, (ast.List, ast.Tuple)):
        return []
    found = []
    for item in expression.elts:
        if isinstance(item, ast.Call) and item.args:
            name = last_name_of(item.args[0]) or "?"
            found.append(MiddlewareInfo(name=name, kind="middleware", options=sorted(keyword_map(item))))
    return found
