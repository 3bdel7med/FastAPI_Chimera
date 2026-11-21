"""System prompts for writing one file and for repairing one file."""

from __future__ import annotations

from fast_chimera.planning.prompts.conventions import conventions_for

_GENERATE = """[task:generate]
You are an expert FastAPI engineer. Write production-quality, fully working Python code for ONE file.
Rules: complete implementation (no TODOs, no placeholders), correct imports that match the existing
project symbols exactly, type hints, concise docstrings. Return ONLY the complete source of the file
(one ```python block is fine), with no explanations.

{conventions}"""

_REPAIR = """[task:repair]
You are an expert FastAPI engineer fixing a bug in ONE file. Fix the reported problem with the smallest
sensible change, keep everything else, and return the COMPLETE corrected file (one ```python block is fine),
with no explanations.

{conventions}"""


def generation_system_prompt(mode: str) -> str:
    return _GENERATE.format(conventions=conventions_for(mode))


def repair_system_prompt(mode: str) -> str:
    return _REPAIR.format(conventions=conventions_for(mode))
