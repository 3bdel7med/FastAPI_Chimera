"""`fast-chimera resume`: continue an interrupted or failed build from its last checkpoint."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

from fast_chimera.cli import dependencies
from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.renderers import render_build_summary
from fast_chimera.cli.ui.reporter import ConsoleReporter
from fast_chimera.cli.ui.runner import run_async_command
from fast_chimera.config import get_settings
from fast_chimera.engine.factory import create_build_engine
from fast_chimera.engine.options import options_for_mode
from fast_chimera.state.repository import JsonStateRepository


def resume(
    path: Path = typer.Argument(Path("."), help="Project directory created by `build` or `add`."),
    no_verify: bool = typer.Option(False, "--no-verify"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Continue an interrupted or failed build."""

    async def operation(reporter: ConsoleReporter) -> None:
        root = path.resolve()
        state = JsonStateRepository(root).load()
        settings = get_settings()

        finished = sum(1 for phase in state.phases if phase.status == "done")
        console.print(f"Resuming {escape(state.catalog.project_name)}: {finished}/{len(state.phases)} phases already done.")

        options = options_for_mode(
            state.mode, verify=not no_verify, batch_size=settings.chimera_batch_size, max_repair_attempts=settings.chimera_repair_attempts
        )
        async with dependencies.create_llm_client(settings) as llm:
            await create_build_engine(root, llm, options, reporter).run(state)
        render_build_summary(state)

    run_async_command(operation, verbose)
