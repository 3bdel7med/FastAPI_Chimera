"""Facts about the generated project skeleton that other modules need to know."""

from __future__ import annotations

from fast_chimera.core.text import package_name

# Files the model must never rewrite: wiring and security code that is deterministic on purpose.
PROTECTED_PATHS = frozenset({"app/main.py", "app/core/config.py", "app/core/database.py", "app/core/security.py", "tests/conftest.py"})

BASELINE_REQUIREMENTS = """fastapi>=0.110
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pydantic>=2.0
pydantic-settings>=2.0
email-validator>=2.0
python-multipart>=0.0.9
pyjwt>=2.8
bcrypt>=4.0
httpx>=0.24
pytest>=7.0
"""

BASELINE_PACKAGES = frozenset(package_name(line) for line in BASELINE_REQUIREMENTS.splitlines() if line.strip())
