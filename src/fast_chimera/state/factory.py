from __future__ import annotations

from fast_chimera.planning.schemas import FeatureCatalog, Roadmap
from fast_chimera.state.models import BuildState, PhaseState


def create_initial_state(request: str, catalog: FeatureCatalog, roadmap: Roadmap, mode: str) -> BuildState:
    """A fresh build: every phase of the roadmap starts as pending."""
    return BuildState(
        mode=mode,  # type: ignore[arg-type]
        prompt=request,
        catalog=catalog,
        phases=[PhaseState(outline=phase) for phase in roadmap.phases],
    )
