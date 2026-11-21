from __future__ import annotations

from dataclasses import dataclass

from fast_chimera.planning.catalog_formatting import describe_for_prompt
from fast_chimera.planning.prompts.conventions import conventions_for
from fast_chimera.planning.prompts.prompt import Prompt
from fast_chimera.planning.schemas import FeatureCatalog, PhaseOutline

_SYSTEM = """[task:plan_phase]
You are a staff backend engineer. List the files needed to implement ONE phase of the roadmap, and nothing
from other phases. Rules:
- Each path is relative, ends with .py and lives under: {allowed_folders}.
- Include a test file for every router. Set `kind` for every file.
- `depends_on` lists paths of files (new or existing) that the file imports from.
- Use action MODIFY only for existing files that must change; otherwise CREATE.
- Never touch protected files: {protected_files}.
- `required_packages` lists packages beyond the baseline (usually an empty list).
- Keep the phase small: about 8 files or fewer.

{conventions}"""


@dataclass(frozen=True)
class PhasePromptInput:
    request: str
    catalog: FeatureCatalog
    roadmap_summary: str
    phase: PhaseOutline
    project_symbols: str
    mode: str
    allowed_folders: str
    protected_files: str


def build_phase_prompt(data: PhasePromptInput) -> Prompt:
    system = _SYSTEM.format(
        allowed_folders=data.allowed_folders,
        protected_files=data.protected_files or "none",
        conventions=conventions_for(data.mode),
    )
    user = (
        f"PRODUCT REQUEST: {data.request}\n\n"
        f"ROADMAP:\n{data.roadmap_summary}\n\n"
        f"PHASE_ID: {data.phase.id}\nPHASE: {data.phase.name}\nGOAL: {data.phase.goal}\n\n"
        f"FEATURES IN SCOPE:\n{describe_for_prompt(data.catalog, data.phase.modules or None)}\n\n"
        f"EXISTING PROJECT SYMBOLS:\n{data.project_symbols or '(empty project)'}"
    )
    return Prompt(system=system, user=user)
