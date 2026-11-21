"""Responsibility: work out how routers are plugged together (`include_router`), so every route
gets its FULL path and the guards inherited from the routers above it."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fast_chimera.shift.extraction.ast_utils import keyword_map
from fast_chimera.shift.extraction.dependencies import dependency_names
from fast_chimera.shift.extraction.imports import module_of_expression
from fast_chimera.shift.extraction.router_nodes import RouterKey, RouterNode, read_prefix
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import GuardInfo


@dataclass
class Include:
    """`parent.include_router(child, prefix=..., dependencies=[...])`"""

    child: RouterKey
    prefix: str
    dependencies: list[str]


@dataclass
class Mount:
    """One place a router is reachable from: the accumulated prefix and the inherited guards."""

    prefix: str
    guards: list[GuardInfo]


class RouterReferences:
    """Turns an expression like `router`, `vendors.router` or an import alias into a RouterKey."""

    def __init__(self, nodes: dict[RouterKey, RouterNode]) -> None:
        self._nodes = nodes

    def key_for(self, module: SourceModule, expression: ast.expr | None) -> RouterKey | None:
        if isinstance(expression, ast.Name):
            return self._key_for_name(module, expression.id)
        if isinstance(expression, ast.Attribute):
            owner_module = module_of_expression(module.imports, expression.value)
            key = (owner_module, expression.attr) if owner_module else None
            return key if key in self._nodes else None
        return None

    def _key_for_name(self, module: SourceModule, name: str) -> RouterKey | None:
        local_key = (module.name, name)
        if local_key in self._nodes:
            return local_key

        imported = module.imports.get(name)
        if imported and imported[1]:  # from some.module import name [as alias]
            imported_key = (imported[0], imported[1])
            if imported_key in self._nodes:
                return imported_key
        return None


class RouterGraph:
    def __init__(self, nodes: dict[RouterKey, RouterNode], includes: dict[RouterKey, list[Include]]) -> None:
        self._nodes = nodes
        self._includes = includes
        self._mounts: dict[RouterKey, list[Mount]] = {}
        for key, node in nodes.items():
            if node.kind == "app":
                self._walk(key, "", [], frozenset({key}))

    @property
    def nodes(self) -> dict[RouterKey, RouterNode]:
        return self._nodes

    def node_for(self, key: RouterKey) -> RouterNode:
        return self._nodes[key]

    def mounts_for(self, key: RouterKey) -> list[Mount]:
        """Empty when no app (through any chain of include_router) reaches this router."""
        return self._mounts.get(key, [])

    def _walk(self, key: RouterKey, prefix: str, guards: list[GuardInfo], path_so_far: frozenset[RouterKey]) -> None:
        self._mounts.setdefault(key, []).append(Mount(prefix, guards))
        for include in self._includes.get(key, []):
            if include.child in path_so_far:
                continue  # an include cycle: stop instead of looping forever
            child = self._nodes[include.child]
            child_guard_names = [*include.dependencies, *child.dependencies]
            self._walk(
                include.child,
                prefix + include.prefix + child.prefix,
                guards + [GuardInfo(name=name, scope="router") for name in child_guard_names],
                path_so_far | {include.child},
            )


def build_router_graph(
    modules: list[SourceModule],
    nodes: dict[RouterKey, RouterNode],
    references: RouterReferences,
    notes: UnresolvedNotes,
) -> RouterGraph:
    includes: dict[RouterKey, list[Include]] = {}
    for module in modules:
        for node in ast.walk(module.tree):
            if not _is_include_router_call(node):
                continue
            call = node  # type: ignore[assignment]
            assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)

            keywords = keyword_map(call)
            child_expression = call.args[0] if call.args else keywords.get("router")
            parent = references.key_for(module, call.func.value)
            child = references.key_for(module, child_expression)

            if parent and child:
                include = Include(child, read_prefix(module, call, notes), dependency_names(keywords.get("dependencies")))
                includes.setdefault(parent, []).append(include)
            elif child_expression is not None:
                notes.add(module.path, call, f"include_router({ast.unparse(child_expression)[:60]}) could not be resolved")
    return RouterGraph(nodes, includes)


def _is_include_router_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router"
