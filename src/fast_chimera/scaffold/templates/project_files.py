"""Top-level files of the generated project."""

from __future__ import annotations

README_MD = """# __PROJECT_NAME__

Generated with [FastChimera](https://pypi.org/project/fast-chimera/). See `FEATURES.md` for the planned feature set.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # also: requirements-extra.txt if present (review it first)
uvicorn app.main:app --reload          # docs at http://127.0.0.1:8000/docs
pytest
```

Set `SECRET_KEY` and `DATABASE_URL` in `.env` (see `.env.example`) before deploying.
"""
