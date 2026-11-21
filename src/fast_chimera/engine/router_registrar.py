"""Responsibility: after a router file is written, register it in the main file."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.analysis.module_analyzer import find_router_variables
from fast_chimera.core.exceptions import AstParsingError
from fast_chimera.core.paths import path_to_module
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.injection.code_injector import CodeInjector
from fast_chimera.planning.schemas import FileSpec


class RouterRegistrar:
    def __init__(self, writer: SafeWriter, main_file: str | None) -> None:
        self._writer = writer
        self._main_file = main_file

    def register(self, spec: FileSpec) -> str | None:
        """Returns a warning message when registration was attempted and failed, else None."""
        if not self._main_file or spec.kind != "router":
            return None

        main_path = Path(self._writer.root) / self._main_file
        source = self._writer.read(spec.path) or ""
        if not main_path.exists() or "router" not in find_router_variables(source):
            return None

        module = path_to_module(spec.path)
        alias = "_".join(module.split(".")[-2:]) + "_router"  # app.routers.vendors -> routers_vendors_router
        try:
            CodeInjector.inject_router(main_path, import_path=module, router_var="router", alias=alias)
        except AstParsingError as error:
            return f"Could not register {spec.path} in {self._main_file}: {error}"
        return None
