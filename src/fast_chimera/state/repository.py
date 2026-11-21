"""Pattern: Repository. The rest of the code asks for a state and saves it; only this class
knows it is a JSON file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from fast_chimera.core.exceptions import StateError
from fast_chimera.state.models import BuildState

STATE_FOLDER = ".fast-chimera"


class StateRepository(Protocol):
    def exists(self) -> bool: ...
    def load(self) -> BuildState: ...
    def save(self, state: BuildState) -> None: ...


class JsonStateRepository:
    def __init__(self, project_root: Path) -> None:
        self.path = Path(project_root) / STATE_FOLDER / "state.json"

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> BuildState:
        if not self.path.exists():
            raise StateError(f"No FastChimera build found here (missing {self.path}).")
        try:
            return BuildState.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError) as error:
            raise StateError(f"Build state is corrupt: {error}") from error

    def save(self, state: BuildState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self.path)  # atomic: a crash never leaves a half-written file
