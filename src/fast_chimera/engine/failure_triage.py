"""Responsibility: look at a failed check's output and decide what to do about it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fast_chimera.verification.traceback_parser import find_missing_module, locate_failing_file

TriageKind = Literal["missing_dependency", "repairable", "unknown"]


@dataclass(frozen=True)
class Triage:
    kind: TriageKind
    module: str | None = None  # for missing_dependency
    file: str | None = None  # for repairable


def triage_failure(output: str, project_root: Path, generated_files: set[str]) -> Triage:
    missing = find_missing_module(output)
    if missing and not _belongs_to_project(missing, project_root):
        return Triage("missing_dependency", module=missing)

    culprit = locate_failing_file(output, project_root, generated_files)
    if culprit:
        return Triage("repairable", file=culprit)
    return Triage("unknown")


def _belongs_to_project(module_name: str, project_root: Path) -> bool:
    top_level = module_name.split(".")[0]
    return (project_root / top_level).is_dir() or (project_root / f"{top_level}.py").is_file()
