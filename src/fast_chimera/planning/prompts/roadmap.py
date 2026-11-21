from __future__ import annotations

from fast_chimera.planning.catalog_formatting import describe_for_prompt
from fast_chimera.planning.prompts.prompt import Prompt
from fast_chimera.planning.schemas import FeatureCatalog

_BUILD_SYSTEM = """[task:roadmap]
You are a staff backend engineer planning an incremental implementation of the product below.
Split the work into ordered phases (between 5 and 14). Rules:
- Foundation first: users/auth, then core entities, then features that depend on them, then cross-cutting
  features (notifications, admin, analytics).
- Every phase is small and cohesive: it will need at most ~8 source files (models, schemas, services,
  routers, tests). Prefer more, smaller phases over a few large ones.
- A phase may depend only on earlier phases.
- `modules` lists the catalog module names a phase covers; every module must be covered by some phase.
- Do not describe files yet, only the goal of each phase."""

_ADD_SYSTEM = """[task:roadmap]
You are a staff backend engineer. The project already exists. Plan ONLY the new work for the request below
as 1-4 small, ordered phases (each at most ~8 files). Reuse what already exists."""


def build_roadmap_prompt(request: str, catalog: FeatureCatalog, mode: str, project_symbols: str) -> Prompt:
    system = _ADD_SYSTEM if mode == "add" else _BUILD_SYSTEM
    user = f"Request: {request}\n\n{describe_for_prompt(catalog)}"
    if project_symbols:
        user += f"\n\nEXISTING PROJECT SYMBOLS:\n{project_symbols}"
    return Prompt(system=system, user=user)
