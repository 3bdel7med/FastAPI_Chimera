"""Responsibility: the LibCST transformer that inserts a router import and its include call.

Edits are idempotent (running twice changes nothing) and keep the file's formatting."""

from __future__ import annotations

import libcst as cst

from fast_chimera.injection.insertion_points import import_insert_index, include_router_insert_index
from fast_chimera.injection.statement_predicates import statement_text


class RouterTransformer(cst.CSTTransformer):
    def __init__(self, import_line: str, include_line: str, app_name: str = "app") -> None:
        super().__init__()
        self._import_line = import_line
        self._include_line = include_line
        self._app_name = app_name
        self.changed = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        body = list(updated_node.body)
        already_there = {statement_text(statement) for statement in body}

        if self._import_line not in already_there:
            body.insert(import_insert_index(body), cst.parse_statement(self._import_line))
            self.changed = True

        if self._include_line not in already_there:
            position = include_router_insert_index(body, self._app_name)
            body.insert(position, cst.parse_statement(self._include_line))
            self.changed = True

        return updated_node.with_changes(body=body)
