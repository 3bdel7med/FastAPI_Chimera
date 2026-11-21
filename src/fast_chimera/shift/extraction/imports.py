"""Responsibility: understand a module's import statements, so `alias.router` can be traced to its real module."""

from __future__ import annotations

import ast

# local name -> (module, attribute). For `import a.b as x` the attribute is None.
ImportMap = dict[str, tuple[str, str | None]]


def collect_imports(module_name: str, is_package: bool, tree: ast.Module) -> ImportMap:
    imports: ImportMap = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = absolute_module_name(module_name, is_package, node.level, node.module)
            for alias in node.names:
                if alias.name != "*":
                    imports[alias.asname or alias.name] = (base, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    imports[alias.asname] = (alias.name, None)
                else:
                    top_level = alias.name.split(".")[0]
                    imports[top_level] = (top_level, None)
    return imports


def absolute_module_name(current_module: str, is_package: bool, level: int, name: str | None) -> str:
    """Resolve `from .x import y` / `from ..x import y` to a full dotted module name."""
    if level == 0:
        return name or ""

    parts = current_module.split(".")
    package_parts = parts if is_package else parts[:-1]
    if level > 1:
        package_parts = package_parts[: max(0, len(package_parts) - (level - 1))]

    base = ".".join(package_parts)
    if name and base:
        return f"{base}.{name}"
    return name or base


def module_of_expression(imports: ImportMap, expression: ast.expr) -> str | None:
    """If `expression` names an imported module (`vendors` or `pkg.vendors`), return its dotted path."""
    if isinstance(expression, ast.Name):
        imported = imports.get(expression.id)
        if imported is None:
            return None
        module, attribute = imported
        return module if attribute is None else f"{module}.{attribute}"

    if isinstance(expression, ast.Attribute):
        parent = module_of_expression(imports, expression.value)
        return f"{parent}.{expression.attr}" if parent else None
    return None
