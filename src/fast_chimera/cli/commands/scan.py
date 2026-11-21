"""`fast-chimera scan`: show the routes and models the tool sees (useful for debugging)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from fast_chimera.analysis.scanner import ProjectScanner
from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.renderers import render_project_summary


def scan(
    path: Path = typer.Argument(Path(".")),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show the routes and models found in a project."""
    summary = ProjectScanner(path).scan()
    if as_json:
        console.print_json(json.dumps(summary.to_dict()))
    else:
        render_project_summary(summary)
