from __future__ import annotations

from pathlib import PurePosixPath

from fast_chimera.core.exceptions import UnsafePathError


def normalize_relative_path(raw: str) -> str:
    """Return a clean POSIX relative path to a .py file, or raise UnsafePathError."""
    cleaned = raw.replace("\\", "/").strip()
    if not cleaned:
        raise UnsafePathError("Empty file path")
    path = PurePosixPath(cleaned)
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise UnsafePathError(f"Unsafe file path: {raw!r}")
    if path.suffix != ".py":
        raise UnsafePathError(f"Only .py files can be generated: {raw!r}")
    return path.as_posix()


def path_to_module(rel_path: str) -> str:
    """'app/models/user.py' -> 'app.models.user' ; 'app/x/__init__.py' -> 'app.x'."""
    parts = PurePosixPath(rel_path).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)
