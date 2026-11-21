"""Plain data describing what the scanner found. No behaviour here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RouteInfo:
    method: str
    path: str
    function: str
    router: str
    module: str


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    fields: list[str]
    kind: str  # orm_model | schema | enum | exception | class
    module: str


@dataclass
class ModuleInfo:
    module: str
    path: str
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    routes: list[RouteInfo] = field(default_factory=list)
    routers: list[str] = field(default_factory=list)


@dataclass
class ProjectSummary:
    root: str
    modules: list[ModuleInfo]
    skipped: list[str]

    @property
    def routes(self) -> list[RouteInfo]:
        return [route for module in self.modules for route in module.routes]

    @property
    def models(self) -> list[ClassInfo]:
        return [c for module in self.modules for c in module.classes if c.kind in ("orm_model", "schema")]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "routes": [asdict(route) for route in self.routes],
            "models": [asdict(model) for model in self.models],
            "skipped": self.skipped,
        }
