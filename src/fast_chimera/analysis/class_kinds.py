"""Responsibility: say what kind of class something is, judging by its base classes."""

from __future__ import annotations


def classify_class(base_names: list[str]) -> str:
    last_segments = [name.split(".")[-1] for name in base_names]

    if any(name in ("Base", "DeclarativeBase") for name in last_segments):
        return "orm_model"
    if "BaseModel" in last_segments:
        return "schema"
    if any(name.endswith("Enum") for name in last_segments):
        return "enum"
    if any(name.endswith(("Exception", "Error")) for name in last_segments):
        return "exception"
    return "class"
