"""Responsibility: write the deterministic project skeleton to disk. Never overwrites existing files."""

from __future__ import annotations

from pathlib import Path

from fast_chimera.scaffold.constants import BASELINE_REQUIREMENTS
from fast_chimera.scaffold.templates.app_files import CONFIG_PY, DATABASE_PY, MAIN_PY, SECURITY_PY
from fast_chimera.scaffold.templates.project_files import README_MD
from fast_chimera.scaffold.templates.test_files import CONFTEST_PY

_GITIGNORE = ".env\n.venv/\n__pycache__/\n*.db\n.pytest_cache/\n.fast-chimera/backups/\n"
_ENV_EXAMPLE = "SECRET_KEY=change-me-in-production\nDATABASE_URL=sqlite:///./app.db\n"
_PYTEST_INI = "[pytest]\npythonpath = .\ntestpaths = tests\n"


def _skeleton_files() -> dict[str, str]:
    """relative path -> content. Empty strings are the `__init__.py` markers."""
    return {
        "app/__init__.py": "",
        "app/main.py": MAIN_PY,
        "app/core/__init__.py": "",
        "app/core/config.py": CONFIG_PY,
        "app/core/database.py": DATABASE_PY,
        "app/core/security.py": SECURITY_PY,
        "app/models/__init__.py": "",
        "app/schemas/__init__.py": "",
        "app/services/__init__.py": "",
        "app/routers/__init__.py": "",
        "tests/__init__.py": "",
        "tests/conftest.py": CONFTEST_PY,
        "pytest.ini": _PYTEST_INI,
        "requirements.txt": BASELINE_REQUIREMENTS,
        ".env.example": _ENV_EXAMPLE,
        ".gitignore": _GITIGNORE,
        "README.md": README_MD,
    }


class Scaffolder:
    def create(self, root: Path, project_name: str) -> list[str]:
        """Write the skeleton and return the relative paths that were created."""
        created: list[str] = []
        for relative_path, content in _skeleton_files().items():
            target = Path(root) / relative_path
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content.replace("__PROJECT_NAME__", project_name), encoding="utf-8")
            created.append(relative_path)
        return created
