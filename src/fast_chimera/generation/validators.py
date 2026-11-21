"""Responsibility: cheap static checks on generated code, before anything is written to disk.

Patterns: Strategy + Chain. Each rule is its own small class with one `check` method;
`ValidatorChain` runs them in order. To add a rule, add a class and put it in the list
(Open/Closed: nothing that already exists has to change)."""

from __future__ import annotations

import ast
from typing import Protocol

from fast_chimera.planning.schemas import FileSpec


class CodeValidator(Protocol):
    def check(self, code: str, spec: FileSpec) -> list[str]:
        """Return a list of problems; an empty list means the code passes this rule."""


class NotEmptyValidator:
    def check(self, code: str, spec: FileSpec) -> list[str]:
        return [] if code.strip() else ["The file is empty."]


class SyntaxValidator:
    def check(self, code: str, spec: FileSpec) -> list[str]:
        try:
            ast.parse(code)
        except SyntaxError as error:
            return [f"SyntaxError on line {error.lineno}: {error.msg}"]
        return []


class RouterValidator:
    """A router file must expose `router`, because the injector registers it by that name."""

    def check(self, code: str, spec: FileSpec) -> list[str]:
        if spec.kind != "router":
            return []
        if _defines_module_level_name(ast.parse(code), "router"):
            return []
        return ["A router module must define a module-level `router = APIRouter(...)`."]


class TestFileValidator:
    __test__ = False  # not a pytest test class, despite the name

    def check(self, code: str, spec: FileSpec) -> list[str]:
        if spec.kind != "test":
            return []
        tree = ast.parse(code)
        has_test_function = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_") for node in ast.walk(tree)
        )
        return [] if has_test_function else ["A test module must contain at least one function named test_*."]


class ValidatorChain:
    """Runs the validators in order and stops at the first one that reports problems.
    Order matters: the syntax check comes first because later rules need parseable code."""

    def __init__(self, validators: list[CodeValidator] | None = None) -> None:
        self._validators = validators or [
            NotEmptyValidator(),
            SyntaxValidator(),
            RouterValidator(),
            TestFileValidator(),
        ]

    def check(self, code: str, spec: FileSpec) -> list[str]:
        for validator in self._validators:
            problems = validator.check(code, spec)
            if problems:
                return problems
        return []


def _defines_module_level_name(tree: ast.Module, name: str) -> bool:
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in statement.targets):
                return True
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == name:
                return True
    return False
