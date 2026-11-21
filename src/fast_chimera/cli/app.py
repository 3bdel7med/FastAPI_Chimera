"""Responsibility: assemble the Typer app. Each command lives in its own module under `commands/`."""

from __future__ import annotations

import typer

from fast_chimera import __version__
from fast_chimera.cli.commands.add import add
from fast_chimera.cli.commands.build import build
from fast_chimera.cli.commands.resume import resume
from fast_chimera.cli.commands.scan import scan
from fast_chimera.cli.commands.shift import shift
from fast_chimera.cli.commands.status import status
from fast_chimera.cli.ui.console import console

app = typer.Typer(
    help="FastChimera: describe a FastAPI product, review the feature list, and build it phase by phase.",
    no_args_is_help=True,
    add_completion=False,
)


def _show_version(value: bool) -> None:
    if value:
        console.print(f"fast-chimera {__version__}")
        raise typer.Exit()


@app.callback()
def main(version: bool = typer.Option(False, "--version", callback=_show_version, is_eager=True, help="Show version.")) -> None:
    """FastChimera."""


for command in (build, resume, add, scan, shift, status):
    app.command()(command)
