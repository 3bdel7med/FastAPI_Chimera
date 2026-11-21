"""Responsibility: answer yes/no questions about top-level statements in a LibCST module body."""

from __future__ import annotations

import libcst as cst

_EMPTY_MODULE = cst.Module([])


def statement_text(node: cst.CSTNode) -> str:
    """The statement as source text, without surrounding whitespace (used to detect duplicates)."""
    return _EMPTY_MODULE.code_for_node(node).strip()


def _simple_items(statement: cst.BaseStatement) -> list[cst.BaseSmallStatement]:
    if isinstance(statement, cst.SimpleStatementLine):
        return list(statement.body)
    return []


def is_import(statement: cst.BaseStatement) -> bool:
    return any(isinstance(item, (cst.Import, cst.ImportFrom)) for item in _simple_items(statement))


def is_docstring(statement: cst.BaseStatement) -> bool:
    items = _simple_items(statement)
    if len(items) != 1 or not isinstance(items[0], cst.Expr):
        return False
    return isinstance(items[0].value, (cst.SimpleString, cst.ConcatenatedString))


def is_app_assignment(statement: cst.BaseStatement, app_name: str) -> bool:
    """True for `app = FastAPI(...)`."""
    for item in _simple_items(statement):
        if not isinstance(item, cst.Assign):
            continue
        for target in item.targets:
            if isinstance(target.target, cst.Name) and target.target.value == app_name:
                return True
    return False


def is_include_router_call(statement: cst.BaseStatement, app_name: str) -> bool:
    """True for `app.include_router(...)`."""
    for item in _simple_items(statement):
        if not isinstance(item, cst.Expr) or not isinstance(item.value, cst.Call):
            continue
        function = item.value.func
        if (
            isinstance(function, cst.Attribute)
            and isinstance(function.value, cst.Name)
            and function.value.value == app_name
            and function.attr.value == "include_router"
        ):
            return True
    return False


def is_main_guard(statement: cst.BaseStatement) -> bool:
    """True for `if __name__ == "__main__":`."""
    return isinstance(statement, cst.If) and "__name__" in statement_text(statement.test)
