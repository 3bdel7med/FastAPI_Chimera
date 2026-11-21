"""What is saved between runs so an interrupted build can resume."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fast_chimera.planning.schemas import FeatureCatalog, FileSpec, PhaseOutline

PhaseStatus = Literal["pending", "planned", "in_progress", "done", "failed"]


class PhaseState(BaseModel):
    outline: PhaseOutline
    status: PhaseStatus = "pending"
    files: list[FileSpec] = Field(default_factory=list)
    completed_files: list[str] = Field(default_factory=list)


class BuildState(BaseModel):
    schema_version: int = 1
    mode: Literal["build", "add"] = "build"
    prompt: str
    catalog: FeatureCatalog
    phases: list[PhaseState]
    file_hashes: dict[str, str] = Field(default_factory=dict)  # files WE wrote -> sha256
    extra_packages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
