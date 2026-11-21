"""`fast-chimera build`: new project from an idea. Features -> roadmap -> phase-by-phase generation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

from fast_chimera.cli import dependencies
from fast_chimera.cli.prompts import ask_feature_selection
from fast_chimera.cli.target_folder import ensure_target_is_free
from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.renderers import render_build_summary, render_catalog, render_next_steps, render_roadmap
from fast_chimera.cli.ui.reporter import ConsoleReporter
from fast_chimera.cli.ui.runner import run_async_command
from fast_chimera.config import get_settings
from fast_chimera.engine.factory import create_build_engine
from fast_chimera.engine.options import options_for_mode
from fast_chimera.planning.planner import Planner
from fast_chimera.planning.schemas import FeatureCatalog, Roadmap
from fast_chimera.scaffold.scaffolder import Scaffolder
from fast_chimera.state.factory import create_initial_state
from fast_chimera.state.repository import JsonStateRepository
from fast_chimera.verification.verifier import ProjectVerifier


def build(
    prompt: list[str] = typer.Argument(..., help="What to build, e.g. 'multi vendor e-commerce website'"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Target directory (default: ./<project-name>)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept the defaults and skip every question."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show features and roadmap, write nothing."),
    batch_size: int | None = typer.Option(None, "--batch-size", min=1, help="Files per verification checkpoint."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip import checks and pytest (they execute generated code)."),
    install: bool = typer.Option(False, "--install", help="pip install the scaffold requirements into THIS Python environment."),
    force: bool = typer.Option(False, "--force", help="Allow overwriting existing files (they are backed up first)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Build a complete project from scratch."""
    request = " ".join(prompt)

    async def operation(reporter: ConsoleReporter) -> None:
        settings = get_settings()
        size = batch_size or settings.chimera_batch_size
        if output and not dry_run:
            ensure_target_is_free(output.resolve())  # fail before spending any LLM calls

        async with dependencies.create_llm_client(settings) as llm:
            planner = Planner(llm)
            catalog = await _discover_features(planner, request, ask_questions=not yes)
            roadmap = await _plan_roadmap(planner, request, catalog, size)

            target = (output or Path.cwd() / catalog.project_name).resolve()
            ensure_target_is_free(target)
            if dry_run:
                console.print("\n[cyan]Dry run: nothing was written.[/cyan]")
                return
            if not yes and not _confirm_build(len(roadmap.phases), target, verifying=not no_verify):
                raise typer.Exit()

            _create_skeleton(target, catalog.project_name, install)
            state = create_initial_state(request, catalog, roadmap, "build")
            JsonStateRepository(target).save(state)

            options = options_for_mode(
                "build", verify=not no_verify, force=force, batch_size=size, max_repair_attempts=settings.chimera_repair_attempts
            )
            await create_build_engine(target, llm, options, reporter).run(state)
            render_build_summary(state)
            render_next_steps(target)

    run_async_command(operation, verbose)


async def _discover_features(planner: Planner, request: str, *, ask_questions: bool) -> FeatureCatalog:
    with console.status("[yellow]Discovering the feature set..."):
        catalog = await planner.discover_features(request)
    render_catalog(catalog)
    return ask_feature_selection(catalog) if ask_questions else catalog.select()


async def _plan_roadmap(planner: Planner, request: str, catalog: FeatureCatalog, batch_size: int) -> Roadmap:
    with console.status("[yellow]Planning the roadmap..."):
        roadmap = await planner.create_roadmap(request, catalog)
    render_roadmap(roadmap, batch_size)
    return roadmap


def _confirm_build(phase_count: int, target: Path, *, verifying: bool) -> bool:
    warning = " Verification executes the generated code on this machine." if verifying else ""
    return typer.confirm(f"\nBuild {phase_count} phases into {target}?{warning}", default=True)


def _create_skeleton(target: Path, project_name: str, install: bool) -> None:
    target.mkdir(parents=True, exist_ok=True)
    created = Scaffolder().create(target, project_name)
    console.print(f"[green]✔[/green] Scaffolded {len(created)} base files in {escape(str(target))}")

    if install:
        with console.status("[yellow]Installing requirements..."):
            result = ProjectVerifier(target).install_requirements()
        if result.ok:
            console.print("[green]✔[/green] Requirements installed")
        else:
            console.print(f"[red]✖[/red] pip failed:\n{escape(result.output[-800:])}")
