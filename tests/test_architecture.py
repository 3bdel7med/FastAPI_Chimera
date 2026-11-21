"""Architecture rules, enforced by a test.

Dependencies must point DOWN (towards the stable, general parts). If one of these tests fails, a module
reached into a layer above it: move the code or introduce an interface instead of importing upwards."""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "fast_chimera"

# layer -> layers it must NOT import from
FORBIDDEN = {
    "core": {"llm", "planning", "analysis", "scaffold", "generation", "injection", "verification", "state", "engine", "shift", "cli"},
    "llm": {"planning", "generation", "engine", "shift", "cli"},
    "planning": {"generation", "injection", "verification", "engine", "shift", "cli"},
    "analysis": {"planning", "generation", "engine", "shift", "cli"},
    "generation": {"engine", "shift", "cli"},
    "injection": {"planning", "generation", "engine", "shift", "cli"},
    "verification": {"planning", "generation", "engine", "shift", "cli"},
    "state": {"generation", "engine", "shift", "cli"},
    "engine": {"shift", "cli"},
    "shift": {"planning", "generation", "engine", "cli"},
}


def imported_layers(layer: str) -> dict[str, set[str]]:
    """file -> the other top-level packages it imports from."""
    found: dict[str, set[str]] = {}
    for file in (PACKAGE_ROOT / layer).rglob("*.py"):
        layers = set()
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("fast_chimera."):
                layers.add(node.module.split(".")[1])
        found[str(file.relative_to(PACKAGE_ROOT))] = layers
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_does_not_import_from_forbidden_layers(layer):
    offenders = {file: sorted(layers & FORBIDDEN[layer]) for file, layers in imported_layers(layer).items() if layers & FORBIDDEN[layer]}
    assert not offenders, f"'{layer}' must not depend on: {offenders}"


def test_no_module_is_too_big_to_read():
    too_long = {
        str(file.relative_to(PACKAGE_ROOT)): len(file.read_text().splitlines())
        for file in PACKAGE_ROOT.rglob("*.py")
        if len(file.read_text().splitlines()) > 200
    }
    assert not too_long, f"split these modules (over 200 lines): {too_long}"
