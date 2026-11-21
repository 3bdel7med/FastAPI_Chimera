"""Responsibility: the interactive questions `build` asks, and the pure logic that interprets the answers."""

from __future__ import annotations

import typer

from fast_chimera.planning.schemas import FeatureCatalog


def parse_module_numbers(answer: str, catalog: FeatureCatalog) -> set[str]:
    """ "2, 5" -> the names of modules number 2 and 5. Invalid numbers are ignored."""
    excluded: set[str] = set()
    for token in answer.replace(" ", "").split(","):
        if token.isdigit() and 1 <= int(token) <= len(catalog.modules):
            excluded.add(catalog.modules[int(token) - 1].name)
    return excluded


def ask_feature_selection(catalog: FeatureCatalog) -> FeatureCatalog:
    answer = typer.prompt("\nModules to EXCLUDE (numbers, comma-separated; Enter keeps all)", default="", show_default=False)
    include_optional = typer.confirm("Include optional features?", default=True)
    return catalog.select(parse_module_numbers(answer, catalog), include_optional)
