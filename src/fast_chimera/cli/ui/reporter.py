"""Responsibility: show engine events in the terminal (the Observer that `engine.events.Reporter` talks to)."""

from __future__ import annotations

from typing import Any

from rich.markup import escape

from fast_chimera.cli.ui.console import console
from fast_chimera.engine.events import Reporter
from fast_chimera.planning.schemas import FileSpec
from fast_chimera.state.models import PhaseState


class ConsoleReporter(Reporter):
    def __init__(self) -> None:
        self._spinner: Any = None

    def phase_started(self, index: int, total: int, phase: PhaseState) -> None:
        console.rule(f"[bold cyan]Phase {index}/{total}: {escape(phase.outline.name)}")
        console.print(f"[dim]{escape(phase.outline.goal)}[/dim]")

    def phase_planned(self, phase: PhaseState, batches: list[list[FileSpec]]) -> None:
        console.print(f"[bold]{len(phase.files)} files in {len(batches)} batch(es)[/bold]")

    def file_started(self, spec: FileSpec) -> None:
        self._stop_spinner()
        self._spinner = console.status(f"[yellow]Generating[/yellow] {escape(spec.path)}")
        self._spinner.start()

    def file_done(self, spec: FileSpec) -> None:
        self._stop_spinner()
        console.print(f"  [green]✔[/green] {escape(spec.path)} [dim]{escape(spec.purpose)}[/dim]")

    def file_skipped(self, spec: FileSpec, reason: str) -> None:
        self._stop_spinner()
        console.print(f"  [yellow]•[/yellow] skipped {escape(spec.path)}: {escape(reason)}")

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        self._stop_spinner()
        mark = "[green]✔[/green]" if ok else "[red]✖[/red]"
        suffix = f" [dim]{escape(detail)}[/dim]" if detail else ""
        console.print(f"  {mark} {escape(label)}{suffix}")

    def warning(self, message: str) -> None:
        self._stop_spinner()
        console.print(f"  [yellow]![/yellow] {escape(message)}")

    def info(self, message: str) -> None:
        self._stop_spinner()
        console.print(f"  [cyan]↻[/cyan] {escape(message)}")

    def close(self) -> None:
        self._stop_spinner()

    def _stop_spinner(self) -> None:
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None
