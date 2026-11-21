"""The coding rules every generation prompt repeats, so all files agree with each other."""

from __future__ import annotations

BUILD_CONVENTIONS = """PROJECT CONVENTIONS (follow strictly; the project was scaffolded already):
- Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0 typed ORM (Mapped / mapped_column).
- Layout: app/models/<name>.py, app/schemas/<name>.py, app/services/<name>.py,
  app/routers/<name>.py, tests/test_<name>.py. Missing __init__.py files are created automatically.
- ORM models: `from app.core.database import Base`; one module per aggregate; give every
  relationship a matching back_populates and use string class names for relationship targets.
- DB session dependency: `from app.core.database import get_db`.
- `app.core.security` already provides hash_password, verify_password, create_access_token, decode_access_token.
- `app.core.config.settings` has: project_name, database_url, secret_key, access_token_expire_minutes.
- NEVER modify the scaffold files (app/main.py, app/core/*, tests/conftest.py). Module-specific
  settings go in the module's own pydantic-settings class.
- Routers expose a module-level `router = APIRouter(prefix="/<resource>", tags=["<resource>"])`.
  They are mounted in app/main.py automatically.
- Tests use the fixtures `client` (TestClient, in-memory SQLite) and `db_session` from tests/conftest.py.
- Use only: fastapi, sqlalchemy, pydantic, pydantic-settings, pyjwt, bcrypt, email-validator,
  python-multipart, httpx, pytest. Anything else must be essential and declared in required_packages.
- Money uses Decimal / Numeric(12, 2). Never hard-code secrets. Validate all input with Pydantic.
- Enforce authorization (ownership / role checks), not just authentication."""

ADD_CONVENTIONS = """PROJECT CONVENTIONS:
- This is an EXISTING project. Match its structure, naming, imports and style (see the symbols list).
- Reuse existing models, schemas, dependencies and helpers instead of redefining them.
- Routers expose a module-level `router = APIRouter(...)`.
- Do not invent packages; anything not already used must be declared in required_packages."""


def conventions_for(mode: str) -> str:
    return ADD_CONVENTIONS if mode == "add" else BUILD_CONVENTIONS
