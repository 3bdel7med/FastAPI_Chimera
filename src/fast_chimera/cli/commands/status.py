"""`fast-chimera status`: show build progress."""

from __future__ import annotations

from pathlib import Path

import typer

from fast_chimera.cli.ui.renderers import render_build_summary
from fast_chimera.cli.ui.runner import print_error
from fast_chimera.core.exceptions import FastChimeraError
from fast_chimera.state.repository import JsonStateRepository


def status(path: Path = typer.Argument(Path("."))) -> None:
    """Show build progress."""
    try:
        state = JsonStateRepository(path.resolve()).load()
    except FastChimeraError as error:
        print_error(error, verbose=False)
        raise typer.Exit(code=1) from None
    render_build_summary(state)
