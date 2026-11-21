from __future__ import annotations

from dataclasses import dataclass

from fast_chimera.planning.schemas import FeatureCatalog, PhaseOutline


@dataclass(frozen=True)
class GenerationContext:
    """Everything the model should know about the project while it writes one file."""

    product_request: str
    catalog: FeatureCatalog
    phase: PhaseOutline
    project_symbols: str
    mode: str = "build"
