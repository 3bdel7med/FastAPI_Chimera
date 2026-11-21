"""Pattern: Facade. `CodeInjector.inject_router` hides reading, parsing, transforming and writing."""

from __future__ import annotations

from pathlib import Path

import libcst as cst

from fast_chimera.core.exceptions import AstParsingError
from fast_chimera.injection.router_transformer import RouterTransformer


class CodeInjector:
    @staticmethod
    def inject_router(
        main_file: str | Path,
        import_path: str,
        router_var: str = "router",
        alias: str | None = None,
        app_var: str = "app",
    ) -> bool:
        """Register a router in the main file. Returns True when the file was changed."""
        path = Path(main_file)
        if not path.exists():
            raise AstParsingError(f"Main file does not exist: {path}")

        alias = alias or router_var
        import_line = f"from {import_path} import {router_var}"
        if alias != router_var:
            import_line += f" as {alias}"
        include_line = f"{app_var}.include_router({alias})"

        try:
            tree = cst.parse_module(path.read_text(encoding="utf-8"))
        except cst.ParserSyntaxError as error:
            raise AstParsingError(f"Cannot parse {path}: {error}") from error

        transformer = RouterTransformer(import_line, include_line, app_var)
        new_tree = tree.visit(transformer)
        if transformer.changed:
            path.write_text(new_tree.code, encoding="utf-8")
        return transformer.changed
