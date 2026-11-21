"""Responsibility: small, pure helpers that clean up and arrange a phase's list of files."""

from __future__ import annotations

from collections.abc import Callable

from fast_chimera.planning.schemas import FileSpec

# Lower number = built earlier when nothing else decides the order.
KIND_ORDER = {"config": 0, "model": 1, "schema": 2, "util": 3, "service": 4, "dependency": 5, "router": 6, "other": 7, "test": 8}


def drop_unusable_files(
    files: list[FileSpec],
    is_allowed: Callable[[str], bool],
    already_exists: Callable[[str], bool],
) -> tuple[list[FileSpec], list[str]]:
    """Remove duplicates and forbidden paths, and dependencies that point nowhere.
    Returns (kept files, forbidden paths that were dropped)."""
    seen_paths: set[str] = set()
    kept: list[FileSpec] = []
    dropped_paths: list[str] = []

    for spec in files:
        if spec.path in seen_paths:
            continue
        seen_paths.add(spec.path)
        if is_allowed(spec.path):
            kept.append(spec)
        else:
            dropped_paths.append(spec.path)

    planned_paths = {spec.path for spec in kept}
    for spec in kept:
        spec.depends_on = [
            dependency
            for dependency in spec.depends_on
            if dependency != spec.path and (dependency in planned_paths or already_exists(dependency))
        ]
    return kept, dropped_paths


def order_by_dependencies(files: list[FileSpec]) -> list[FileSpec]:
    """Dependencies first (so a file can import what it needs); otherwise models before routers before tests."""
    by_path = {spec.path: spec for spec in files}
    ordered: list[FileSpec] = []
    visited: set[str] = set()

    def place(spec: FileSpec) -> None:
        if spec.path in visited:  # also protects against dependency cycles
            return
        visited.add(spec.path)
        for dependency in spec.depends_on:
            if dependency in by_path:
                place(by_path[dependency])
        ordered.append(spec)

    for spec in sorted(files, key=lambda s: (KIND_ORDER.get(s.kind, 7), s.path)):
        place(spec)
    return ordered


def split_into_batches(files: list[FileSpec], batch_size: int) -> list[list[FileSpec]]:
    size = max(1, batch_size)
    return [files[start : start + size] for start in range(0, len(files), size)]
