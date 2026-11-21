"""`fast-chimera shift`: fingerprint the project, save it locally, send it to the configured server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

from fast_chimera.cli import dependencies
from fast_chimera.cli.ui.console import console
from fast_chimera.cli.ui.renderers import render_fingerprint_summary
from fast_chimera.cli.ui.runner import print_error
from fast_chimera.core.exceptions import FastChimeraError
from fast_chimera.shift.extraction import FingerprintExtractor
from fast_chimera.shift.publishing import display_url, load_shift_settings
from fast_chimera.shift.schema import Fingerprint

DEFAULT_FILE_NAME = "fast-chimera.shift.json"
_SEND_FAILURE_MARKERS = ("Sending failed", "rejected", "redirected")


def shift(
    path: Path = typer.Argument(Path("."), help="FastAPI project to fingerprint."),
    output: Path | None = typer.Option(None, "--output", "-o", help=f"Where to save the JSON (default: <path>/{DEFAULT_FILE_NAME})."),
    server: str | None = typer.Option(None, "--server", help="Send to this URL instead of SHIFT_SERVER_URL from .env."),
    no_send: bool = typer.Option(False, "--no-send", help="Only save the file locally."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="List everything that could not be resolved."),
) -> None:
    """Fingerprint the project (tables, relations, endpoints, middleware) and send it to your server."""
    root = path.resolve()
    try:
        fingerprint = FingerprintExtractor(root).extract()
        saved_to = _save_locally(fingerprint, (output or root / DEFAULT_FILE_NAME).resolve())
        render_fingerprint_summary(fingerprint, saved_to, show_all_notes=verbose)
        if not no_send:
            _send(fingerprint, root, server)
    except FastChimeraError as error:
        print_error(error, verbose)
        if any(marker in str(error) for marker in _SEND_FAILURE_MARKERS):
            console.print("[dim]The fingerprint file was saved locally; run `fast-chimera shift` again to retry.[/dim]")
        raise typer.Exit(code=1) from None


def _save_locally(fingerprint: Fingerprint, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(fingerprint.to_json(), encoding="utf-8")
    temporary.replace(target)  # atomic replace
    return target


def _send(fingerprint: Fingerprint, root: Path, server_override: str | None) -> None:
    settings = load_shift_settings(root)
    url = settings.server_url(server_override)
    if not url:
        console.print("[dim]No SHIFT_SERVER_URL in .env: saved locally only.[/dim]")
        return

    with console.status(f"[yellow]Sending to {escape(display_url(url))}..."):
        result = dependencies.create_publisher(settings).send(fingerprint, url)

    remote = f" (id {escape(result.remote_id)})" if result.remote_id else ""
    console.print(f"[green]✔[/green] Sent to {escape(result.destination)}: HTTP {result.status_code}{remote}")
