"""Responsibility: turn every `@router.get(...)`-style decorator into EndpointInfo objects."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fast_chimera.analysis.module_analyzer import HTTP_METHODS
from fast_chimera.shift.extraction.ast_utils import is_none_constant, keyword_map, shorten, string_list, string_value
from fast_chimera.shift.extraction.dependencies import dependency_names
from fast_chimera.shift.extraction.params import FunctionNode, ParameterAnalyzer
from fast_chimera.shift.extraction.router_graph import Mount, RouterGraph, RouterReferences
from fast_chimera.shift.extraction.router_nodes import RouterKey
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import EndpointInfo, GuardInfo

ROUTE_DECORATORS = HTTP_METHODS | {"websocket", "api_route"}


@dataclass
class _RouteDecorator:
    owner: RouterKey | None  # the router/app the decorator belongs to, if we can identify it
    owner_text: str
    decorator_name: str  # get, post, websocket, api_route...
    path: str
    keywords: dict[str, ast.expr]


@dataclass
class _Placement:
    """Where a route is reachable from."""

    mounts: list[Mount]
    router_tags: list[str]
    mounted: bool


class EndpointExtractor:
    def __init__(self, graph: RouterGraph, references: RouterReferences, parameters: ParameterAnalyzer, notes: UnresolvedNotes) -> None:
        self._graph = graph
        self._references = references
        self._parameters = parameters
        self._notes = notes

    def extract(self, modules: list[SourceModule]) -> list[EndpointInfo]:
        endpoints: list[EndpointInfo] = []
        for module in modules:
            for node in ast.walk(module.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        endpoints += self._endpoints_from_decorator(module, node, decorator)
        return endpoints

    def _endpoints_from_decorator(self, module: SourceModule, function: FunctionNode, decorator: ast.expr) -> list[EndpointInfo]:
        route = self._read_decorator(module, function, decorator)
        if route is None:
            return []

        placement = self._place(module, function, decorator, route)
        analysis = self._parameters.analyze(function, route.path)
        own_guards = [GuardInfo(name=name, scope="endpoint") for name in dependency_names(route.keywords.get("dependencies"))]
        tags = list(dict.fromkeys([*placement.router_tags, *string_list(route.keywords.get("tags"))]))

        return [
            EndpointInfo(
                method=method,
                path=(mount.prefix + route.path) or "/",
                handler=function.name,
                module=module.name,
                tags=tags,
                guards=[*mount.guards, *own_guards],
                injects=analysis.injects,
                params=analysis.params,
                request_body=analysis.request_body,
                response_model=self._response_model(function, route),
                status_code=_status_code(route.keywords.get("status_code")),
                mounted=placement.mounted,
            )
            for mount in placement.mounts
            for method in self._http_methods(route)
        ]

    def _read_decorator(self, module: SourceModule, function: FunctionNode, decorator: ast.expr) -> _RouteDecorator | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None
        name = decorator.func.attr
        if name not in ROUTE_DECORATORS:
            return None

        keywords = keyword_map(decorator)
        path_expression = decorator.args[0] if decorator.args else keywords.get("path")
        path = string_value(path_expression)
        owner = self._references.key_for(module, decorator.func.value)

        if path is None:
            if owner:
                self._notes.add(module.path, decorator, f"{function.name}: route path is not a constant string")
            return None
        if owner is None and not (path.startswith("/") or path == ""):
            return None  # some unrelated object that happens to have a `.get(...)` method

        return _RouteDecorator(owner, ast.unparse(decorator.func.value), name, path, keywords)

    def _place(self, module: SourceModule, function: FunctionNode, decorator: ast.expr, route: _RouteDecorator) -> _Placement:
        if route.owner is None:
            self._notes.add(
                module.path, decorator, f"{function.name}: '{shorten(route.owner_text)}' is not a known FastAPI/APIRouter instance"
            )
            return _Placement([Mount("", [])], [], mounted=False)

        node = self._graph.node_for(route.owner)
        mounts = self._graph.mounts_for(route.owner)
        if mounts:
            return _Placement(mounts, node.tags, mounted=True)

        # Declared, but no app includes it: keep the route, flagged as not mounted.
        self._notes.add(module.path, decorator, f"{function.name}: router '{route.owner[1]}' is never included by an app")
        guards = [GuardInfo(name=name, scope="router") for name in node.dependencies]
        return _Placement([Mount(node.prefix, guards)], node.tags, mounted=False)

    @staticmethod
    def _http_methods(route: _RouteDecorator) -> list[str]:
        if route.decorator_name == "api_route":
            return [method.upper() for method in string_list(route.keywords.get("methods"))] or ["GET"]
        if route.decorator_name == "websocket":
            return ["WEBSOCKET"]
        return [route.decorator_name.upper()]

    @staticmethod
    def _response_model(function: FunctionNode, route: _RouteDecorator) -> str | None:
        declared = route.keywords.get("response_model")
        if declared is not None:
            return shorten(ast.unparse(declared))
        if function.returns is not None and not is_none_constant(function.returns):
            return shorten(ast.unparse(function.returns))
        return None


def _status_code(expression: ast.expr | None) -> int | None:
    """`201` or `status.HTTP_201_CREATED` -> 201."""
    if expression is None:
        return None
    if isinstance(expression, ast.Constant) and isinstance(expression.value, int):
        return expression.value
    digits = [part for part in ast.unparse(expression).replace("_", " ").split() if part.isdigit() and len(part) == 3]
    return int(digits[0]) if digits else None
