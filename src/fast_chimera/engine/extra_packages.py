"""Responsibility: remember packages the model asked for, and write them to requirements-extra.txt.

They are NEVER installed automatically: package names suggested by a model must be reviewed by a human."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.core.text import package_name
from fast_chimera.scaffold.constants import BASELINE_PACKAGES
from fast_chimera.state.models import BuildState

EXTRA_REQUIREMENTS_FILE = "requirements-extra.txt"
REVIEW_WARNING = "Review requirements-extra.txt before installing: these packages were suggested by the model."


def remember_packages(state: BuildState, requested: list[str]) -> None:
    already_known = {package_name(package) for package in state.extra_packages}
    for requirement in requested:
        name = package_name(requirement)
        if not name or name in BASELINE_PACKAGES or name in already_known:
            continue
        state.extra_packages.append(requirement)
        already_known.add(name)


def write_requirements_file(project_root: Path, state: BuildState) -> bool:
    """Returns True when a file was written."""
    if not state.extra_packages:
        return False
    content = "\n".join(state.extra_packages) + "\n"
    (Path(project_root) / EXTRA_REQUIREMENTS_FILE).write_text(content, encoding="utf-8")
    return True
