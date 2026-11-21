"""Responsibility: decide WHERE in a module body new lines should go. Pure functions, no editing."""

from __future__ import annotations

from collections.abc import Sequence

import libcst as cst

from fast_chimera.injection import statement_predicates as is_


def import_insert_index(body: Sequence[cst.BaseStatement]) -> int:
    """After the last import; otherwise after the module docstring; otherwise at the top."""
    last_import = -1
    for index, statement in enumerate(body):
        if is_.is_import(statement):
            last_import = index
    if last_import != -1:
        return last_import + 1
    if body and is_.is_docstring(body[0]):
        return 1
    return 0


def include_router_insert_index(body: Sequence[cst.BaseStatement], app_name: str) -> int:
    """After the last existing include_router; else right after `app = FastAPI(...)`;
    else before `if __name__ == "__main__"`; else at the end."""
    include_positions = [i for i, s in enumerate(body) if is_.is_include_router_call(s, app_name)]
    if include_positions:
        return include_positions[-1] + 1

    app_positions = [i for i, s in enumerate(body) if is_.is_app_assignment(s, app_name)]
    if app_positions:
        return app_positions[0] + 1

    guard_positions = [i for i, s in enumerate(body) if is_.is_main_guard(s)]
    if guard_positions:
        return guard_positions[0]

    return len(body)
