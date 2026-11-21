"""Responsibility: describe a route handler's parameters (path, query, body, file...), what it
injects with Depends(...), and which parameter is the request body."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Literal

from fast_chimera.shift.extraction.annotations import annotated_metadata_calls, strip_annotated, unwrap_annotation
from fast_chimera.shift.extraction.ast_utils import last_name_of, shorten
from fast_chimera.shift.extraction.class_index import ClassIndex
from fast_chimera.shift.extraction.dependencies import dependency_target, is_dependency_call
from fast_chimera.shift.schema import ParamInfo

Location = Literal["path", "query", "header", "cookie", "form", "file", "body"]

LOCATION_FUNCTIONS: dict[str, Location] = {
    "Query": "query",
    "Path": "path",
    "Header": "header",
    "Cookie": "cookie",
    "Body": "body",
    "Form": "form",
    "File": "file",
}
IGNORED_TYPES = frozenset({"Request", "Response", "BackgroundTasks", "WebSocket", "HTTPConnection", "SecurityScopes"})
_PATH_PARAMETER = re.compile(r"\{(\w+)(?::[^}]*)?\}")

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class ParameterAnalysis:
    params: list[ParamInfo] = field(default_factory=list)
    injects: list[str] = field(default_factory=list)
    request_body: str | None = None


class ParameterAnalyzer:
    def __init__(self, class_index: ClassIndex) -> None:
        self._classes = class_index

    def analyze(self, function: FunctionNode, route_path: str) -> ParameterAnalysis:
        path_names = set(_PATH_PARAMETER.findall(route_path))
        analysis = ParameterAnalysis()
        for argument, default in _arguments_with_defaults(function.args):
            if argument.arg not in ("self", "cls"):
                self._analyze_argument(argument, default, path_names, analysis)
        return analysis

    def _analyze_argument(self, argument: ast.arg, default: ast.expr | None, path_names: set[str], analysis: ParameterAnalysis) -> None:
        annotation = unwrap_annotation(argument.annotation) if argument.annotation is not None else None
        type_name = last_name_of(annotation.core) if annotation and annotation.core is not None else None

        # Calls that can appear as the default value or inside Annotated[...]
        calls = [c for c in [default, *annotated_metadata_calls(argument.annotation)] if isinstance(c, ast.Call)]

        dependency_call = next((c for c in calls if is_dependency_call(c)), None)
        if dependency_call is not None:
            analysis.injects.append(self._describe_dependency(dependency_call, type_name))
            return
        if type_name in IGNORED_TYPES:
            return

        field_call = next((c for c in calls if last_name_of(c.func) in LOCATION_FUNCTIONS), None)
        location = self._decide_location(argument.arg, type_name, field_call, path_names)
        type_text = shorten(ast.unparse(strip_annotated(argument.annotation))) if argument.annotation is not None else None

        analysis.params.append(
            ParamInfo(name=argument.arg, location=location, type=type_text, required=_is_required(default, field_call, location))
        )
        if location == "body" and analysis.request_body is None:
            analysis.request_body = type_text

    @staticmethod
    def _describe_dependency(call: ast.Call, type_name: str | None) -> str:
        target = dependency_target(call)
        if target is not None:
            return shorten(ast.unparse(target))
        return type_name or "?"  # bare `Depends()`: the annotation is the dependency

    def _decide_location(self, name: str, type_name: str | None, field_call: ast.Call | None, path_names: set[str]) -> Location:
        if field_call is not None:
            return LOCATION_FUNCTIONS[last_name_of(field_call.func) or ""]
        if name in path_names:
            return "path"
        if type_name == "UploadFile":
            return "file"
        if self._classes.is_schema(type_name):
            return "body"
        return "query"


def _is_required(default: ast.expr | None, field_call: ast.Call | None, location: Location) -> bool:
    if default is None or location == "path":
        return True
    if field_call is not None and field_call is default:
        first_argument = field_call.args[0] if field_call.args else None
        is_ellipsis = isinstance(first_argument, ast.Constant) and first_argument.value is Ellipsis
        has_default_keyword = any(keyword.arg == "default" for keyword in field_call.keywords)
        return is_ellipsis and not has_default_keyword  # Query(...) means required
    return False


def _arguments_with_defaults(arguments: ast.arguments) -> list[tuple[ast.arg, ast.expr | None]]:
    """Pair every parameter with its default value (or None)."""
    positional = [*arguments.posonlyargs, *arguments.args]
    missing_defaults: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults))
    positional_pairs = list(zip(positional, missing_defaults + list(arguments.defaults), strict=True))
    keyword_only_pairs = list(zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True))
    return positional_pairs + keyword_only_pairs
