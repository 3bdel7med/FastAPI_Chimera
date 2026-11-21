"""Responsibility: render a FeatureCatalog as text (for prompts) or Markdown (for FEATURES.md).

Kept out of the pydantic model on purpose: the model describes data, this module decides
how that data is presented."""

from __future__ import annotations

from collections.abc import Iterable

from fast_chimera.planning.schemas import FeatureCatalog


def describe_for_prompt(catalog: FeatureCatalog, focus_modules: Iterable[str] | None = None) -> str:
    """Every module by name; the features are listed only for the modules in focus (or all)."""
    focus = {name.strip().lower() for name in focus_modules} if focus_modules else None

    lines = [f"Product: {catalog.project_name} - {catalog.summary}", "Modules:"]
    for module in catalog.modules:
        lines.append(f"- {module.name}: {module.description}")
        in_focus = focus is None or module.name.lower() in focus
        if in_focus:
            for feature in module.features:
                lines.append(f"    * [{feature.priority}] {feature.name}: {feature.description}")
    return "\n".join(lines)


def to_markdown(catalog: FeatureCatalog) -> str:
    lines = [f"# {catalog.project_name}: planned features", "", catalog.summary, ""]
    for module in catalog.modules:
        lines += [f"## {module.name}", module.description, ""]
        for feature in module.features:
            lines.append(f"- **{feature.name}** ({feature.priority}): {feature.description}")
        lines.append("")
    return "\n".join(lines)
