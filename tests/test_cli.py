import pytest
from typer.testing import CliRunner

pytest.importorskip("fastapi")

from fast_chimera.cli import dependencies  # noqa: E402
from fast_chimera.cli.app import app as cli_app  # noqa: E402
from fast_chimera.config import get_settings  # noqa: E402

from .fakes import FakeLlm  # noqa: E402

runner = CliRunner()


@pytest.fixture(autouse=True)
def fake_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(dependencies, "create_llm_client", lambda settings: FakeLlm())


def test_help_works_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0 and "build" in result.output


def test_dry_run_shows_features_and_roadmap_and_writes_nothing(tmp_path):
    out = tmp_path / "shop"
    result = runner.invoke(cli_app, ["build", "mini", "marketplace", "--dry-run", "--yes", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "Vendor registration" in result.output and "Roadmap: 2 phases" in result.output
    assert not out.exists()


def test_interactive_exclusion_and_full_build_then_status_and_scan(tmp_path):
    out = tmp_path / "shop"
    # exclude module 2 (Products), drop optional features, confirm the build
    result = runner.invoke(cli_app, ["build", "mini marketplace", "-o", str(out), "--no-verify"], input="2\nn\ny\n")
    assert result.exit_code == 0, result.output
    assert (out / "app/main.py").exists() and (out / ".fast-chimera/state.json").exists()

    status = runner.invoke(cli_app, ["status", str(out)])
    assert status.exit_code == 0 and "phases complete" in status.output

    scan = runner.invoke(cli_app, ["scan", str(out)])
    assert "/health" in scan.output


def test_refuses_to_build_into_a_non_empty_directory(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    result = runner.invoke(cli_app, ["build", "x", "--yes", "-o", str(tmp_path)])
    assert "Vendor registration" not in result.output  # rejected before any planning happened
    assert result.exit_code == 1 and "not empty" in " ".join(result.output.split())


def test_missing_api_key_gives_friendly_error(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    result = runner.invoke(cli_app, ["build", "x", "--yes"])
    assert result.exit_code == 1 and "GEMINI_API_KEY" in result.output
