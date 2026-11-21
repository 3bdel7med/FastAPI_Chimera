"""The ordered list of phases a project is built in."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhaseOutline(BaseModel):
    id: int = 0
    name: str
    goal: str
    modules: list[str] = Field(default_factory=list, description="Catalog module names covered by this phase")


class Roadmap(BaseModel):
    phases: list[PhaseOutline] = Field(min_length=1)

    def renumbered(self) -> Roadmap:
        """Phase ids are ours to assign (1, 2, 3...), whatever the model wrote."""
        for number, phase in enumerate(self.phases, start=1):
            phase.id = number
        return self
