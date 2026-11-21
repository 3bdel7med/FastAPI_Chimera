from __future__ import annotations

from dataclasses import dataclass

from fast_chimera.scaffold.constants import PROTECTED_PATHS


@dataclass(frozen=True)
class EngineOptions:
    verify: bool = True
    force: bool = False
    batch_size: int = 4
    max_repair_attempts: int = 2
    protected_paths: frozenset[str] = PROTECTED_PATHS
    allowed_folders: tuple[str, ...] | None = ("app", "tests")
    main_file: str | None = "app/main.py"

    @classmethod
    def for_new_project(cls, *, verify: bool, force: bool, batch_size: int, max_repair_attempts: int) -> EngineOptions:
        """A freshly scaffolded project: the scaffold is protected, generation stays in app/ and tests/."""
        return cls(verify=verify, force=force, batch_size=batch_size, max_repair_attempts=max_repair_attempts)

    @classmethod
    def for_existing_project(cls, *, verify: bool, batch_size: int, max_repair_attempts: int) -> EngineOptions:
        """Someone else's layout: nothing is protected by name and any folder is allowed."""
        return cls(
            verify=verify,
            batch_size=batch_size,
            max_repair_attempts=max_repair_attempts,
            protected_paths=frozenset(),
            allowed_folders=None,
        )


def options_for_mode(mode: str, *, verify: bool, batch_size: int, max_repair_attempts: int, force: bool = False) -> EngineOptions:
    """`build` and `add` follow different safety rules; the saved state remembers which one is in use."""
    if mode == "add":
        return EngineOptions.for_existing_project(verify=verify, batch_size=batch_size, max_repair_attempts=max_repair_attempts)
    return EngineOptions.for_new_project(verify=verify, force=force, batch_size=batch_size, max_repair_attempts=max_repair_attempts)
