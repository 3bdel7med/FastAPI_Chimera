"""Responsibility: run a command's async work and turn errors into friendly messages and exit codes.

Expected errors (FastChimeraError) print a short message. Anything else is a bug and keeps its traceback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import typer
from rich.markup import escape

from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.reporter import ConsoleReporter
from fast_chimera.core.exceptions import FastChimeraError

INTERRUPTED_EXIT_CODE = 130


def run_async_command(operation: Callable[[ConsoleReporter], Coroutine[Any, Any, None]], verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    reporter = ConsoleReporter()
    try:
        asyncio.run(operation(reporter))
    except FastChimeraError as error:
        reporter.close()
        print_error(error, verbose)
        raise typer.Exit(code=1) from None
    except KeyboardInterrupt:
        reporter.close()
        console.print("\n[yellow]Interrupted. Progress is saved; continue with `fast-chimera resume`.[/yellow]")
        raise typer.Exit(code=INTERRUPTED_EXIT_CODE) from None
    finally:
        reporter.close()


def print_error(error: Exception, verbose: bool) -> None:
    console.print(f"\n[bold red]Error:[/bold red] {escape(str(error))}")
    if verbose:
        console.print_exception()
