"""`fast-chimera add`: add a feature to an existing project using the same phased engine."""

from __future__ import annotations

from pathlib import Path

import typer

from fast_chimera.analysis.scanner import ProjectScanner
from fast_chimera.analysis.symbol_index import format_symbol_index
from fast_chimera.cli import dependencies
from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.renderers import render_build_summary, render_roadmap
from fast_chimera.cli.ui.reporter import ConsoleReporter
from fast_chimera.cli.ui.runner import run_async_command
from fast_chimera.config import get_settings
from fast_chimera.engine.factory import create_build_engine
from fast_chimera.engine.options import options_for_mode
from fast_chimera.planning.planner import Planner
from fast_chimera.planning.schemas import FeatureCatalog
from fast_chimera.state.factory import create_initial_state
from fast_chimera.state.repository import JsonStateRepository


def add(
    prompt: list[str] = typer.Argument(..., help="Feature to add, e.g. 'wishlist endpoints for customers'"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Existing FastAPI project."),
    yes: bool = typer.Option(False, "--yes", "-y"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Add a feature to an existing project."""
    request = " ".join(prompt)

    async def operation(reporter: ConsoleReporter) -> None:
        root = path.resolve()
        settings = get_settings()
        catalog = FeatureCatalog.from_request(request)

        async with dependencies.create_llm_client(settings) as llm:
            symbols = format_symbol_index(ProjectScanner(root).scan())
            with console.status("[yellow]Planning..."):
                roadmap = await Planner(llm).create_roadmap(request, catalog, mode="add", project_symbols=symbols)
            render_roadmap(roadmap, settings.chimera_batch_size)

            question = f"\nApply {len(roadmap.phases)} phase(s) to {root}? Existing files are backed up before changes."
            if not yes and not typer.confirm(question, default=True):
                raise typer.Exit()

            state = create_initial_state(request, catalog, roadmap, "add")
            JsonStateRepository(root).save(state)
            options = options_for_mode(
                "add", verify=not no_verify, batch_size=settings.chimera_batch_size, max_repair_attempts=settings.chimera_repair_attempts
            )
            await create_build_engine(root, llm, options, reporter).run(state)
        render_build_summary(state)

    run_async_command(operation, verbose)
