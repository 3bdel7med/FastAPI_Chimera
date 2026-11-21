"""Responsibility: draw tables, trees and panels. Pure presentation: no decisions, no I/O besides printing."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from fast_chimera.analysis.models import ProjectSummary
from fast_chimera.cli.ui.console import console
from fast_chimera.planning.schemas import FeatureCatalog, Roadmap
from fast_chimera.shift.schema import Fingerprint
from fast_chimera.state.models import BuildState

_PRIORITY_STYLE = {"core": "bold green", "recommended": "yellow", "optional": "dim"}
_STATUS_STYLE = {"done": "green", "failed": "red", "in_progress": "yellow", "planned": "cyan", "pending": "dim"}


def render_catalog(catalog: FeatureCatalog) -> None:
    title = f"{catalog.total_features} features in {len(catalog.modules)} modules"
    console.print(Panel(f"[bold]{escape(catalog.project_name)}[/bold]\n{escape(catalog.summary)}", title=title, border_style="cyan"))

    tree = Tree("Feature catalog")
    for number, module in enumerate(catalog.modules, start=1):
        branch = tree.add(f"[bold]{number}. {escape(module.name)}[/bold] [dim]{escape(module.description)}[/dim]")
        for feature in module.features:
            style = _PRIORITY_STYLE[feature.priority]
            branch.add(f"[{style}]{feature.priority:<11}[/] {escape(feature.name)} [dim]{escape(feature.description)}[/dim]")
    console.print(tree)


def render_roadmap(roadmap: Roadmap, batch_size: int) -> None:
    table = Table(title=f"Roadmap: {len(roadmap.phases)} phases (each planned and generated separately)")
    table.add_column("#", justify="right")
    table.add_column("Phase", style="bold")
    table.add_column("Goal")
    table.add_column("Modules", style="dim")
    for phase in roadmap.phases:
        table.add_row(str(phase.id), escape(phase.name), escape(phase.goal), escape(", ".join(phase.modules)))
    console.print(table)
    console.print(f"[dim]Files are generated one at a time, checkpointed every {batch_size} files.[/dim]")


def render_build_summary(state: BuildState) -> None:
    done = sum(1 for phase in state.phases if phase.status == "done")
    table = Table(title=f"{done}/{len(state.phases)} phases complete, {len(state.file_hashes)} files written")
    table.add_column("#", justify="right")
    table.add_column("Phase")
    table.add_column("Status")
    table.add_column("Files", justify="right")
    for phase in state.phases:
        style = _STATUS_STYLE[phase.status]
        table.add_row(str(phase.outline.id), escape(phase.outline.name), f"[{style}]{phase.status}[/]", str(len(phase.completed_files)))
    console.print(table)

    if state.warnings:
        console.print("[bold yellow]Warnings[/bold yellow]")
        for warning in state.warnings:
            console.print(f"  [yellow]![/yellow] {escape(warning)}")


def render_next_steps(target: Path) -> None:
    commands = (
        f"cd {escape(str(target))}\npython -m venv .venv && source .venv/bin/activate\n"
        "pip install -r requirements.txt\nuvicorn app.main:app --reload"
    )
    console.print(Panel(commands, title="Next steps", border_style="green"))


def render_project_summary(summary: ProjectSummary) -> None:
    routes = Table(title=f"{len(summary.routes)} routes")
    for column in ("Method", "Path", "Handler", "Module"):
        routes.add_column(column)
    for route in summary.routes:
        routes.add_row(route.method, escape(route.path), route.function, route.module)
    console.print(routes)

    models = Table(title=f"{len(summary.models)} models / schemas")
    for column in ("Class", "Kind", "Fields"):
        models.add_column(column)
    for model in summary.models:
        models.add_row(model.name, model.kind, escape(", ".join(model.fields)))
    console.print(models)

    for skipped in summary.skipped:
        console.print(f"[yellow]Skipped (syntax error):[/yellow] {escape(skipped)}")


def render_fingerprint_summary(fingerprint: Fingerprint, saved_to: Path, show_all_notes: bool) -> None:
    stats = fingerprint.stats()
    table = Table(title=f"Fingerprint of {escape(fingerprint.project)}")
    table.add_column("Item")
    table.add_column("Count", justify="right")
    for key in ("tables", "columns", "relations", "endpoints", "middleware", "unresolved"):
        table.add_row(key, str(stats[key]))
    console.print(table)
    console.print(f"[green]✔[/green] Saved {escape(str(saved_to))} [dim](sha256 {fingerprint.content_sha256[:12]}…)[/dim]")

    notes = fingerprint.unresolved if show_all_notes else fingerprint.unresolved[:5]
    for note in notes:
        console.print(f"  [yellow]![/yellow] {escape(note)}")
    hidden = len(fingerprint.unresolved) - len(notes)
    if hidden > 0:
        console.print(f"  [dim]… {hidden} more (use --verbose)[/dim]")
