"""The files a single phase will create or modify."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from fast_chimera.core.exceptions import UnsafePathError
from fast_chimera.core.paths import normalize_relative_path

FileKind = Literal["model", "schema", "service", "router", "dependency", "util", "config", "test", "other"]
FileAction = Literal["CREATE", "MODIFY"]

_KNOWN_KINDS = ("model", "schema", "service", "router", "dependency", "util", "config", "test")
_PACKAGE_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,_-]+\])?([<>=!~]=?[A-Za-z0-9.*]+(,[<>=!~]=?[A-Za-z0-9.*]+)*)?$"
)


class FileSpec(BaseModel):
    path: str = Field(description="Relative path such as app/models/vendor.py")
    purpose: str
    action: FileAction = "CREATE"
    kind: FileKind = "other"
    depends_on: list[str] = Field(default_factory=list, description="Paths of files this file imports from")

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        text = str(value).strip().upper()
        return text if text in ("CREATE", "MODIFY") else "CREATE"

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: Any) -> str:
        text = str(value).strip().lower()
        return text if text in _KNOWN_KINDS else "other"

    @field_validator("path")
    @classmethod
    def _check_path(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("depends_on")
    @classmethod
    def _keep_safe_dependencies(cls, value: list[str]) -> list[str]:
        safe_paths = []
        for dependency in value:
            try:
                safe_paths.append(normalize_relative_path(dependency))
            except UnsafePathError:
                continue
        return safe_paths


def _has_safe_path(item: Any) -> bool:
    raw_path = item.get("path") if isinstance(item, dict) else getattr(item, "path", None)
    if not isinstance(raw_path, str):
        return False
    try:
        normalize_relative_path(raw_path)
    except UnsafePathError:
        return False
    return True


class PhasePlan(BaseModel):
    files: list[FileSpec] = Field(min_length=1)
    required_packages: list[str] = Field(default_factory=list)

    @field_validator("files", mode="before")
    @classmethod
    def _drop_files_with_unsafe_paths(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [item for item in value if _has_safe_path(item)]

    @field_validator("required_packages")
    @classmethod
    def _keep_valid_package_names(cls, value: list[str]) -> list[str]:
        cleaned = [name.strip() for name in value]
        return [name for name in cleaned if _PACKAGE_REQUIREMENT.match(name)]
