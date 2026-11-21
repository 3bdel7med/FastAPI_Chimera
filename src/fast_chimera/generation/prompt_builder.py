"""Responsibility: assemble the user-message text for "write this file" and "fix this file"."""

from __future__ import annotations

from fast_chimera.generation.context import GenerationContext
from fast_chimera.generation.dependency_sources import DependencySourceReader
from fast_chimera.planning.catalog_formatting import describe_for_prompt
from fast_chimera.planning.schemas import FileSpec


class FilePromptBuilder:
    def __init__(self, dependency_reader: DependencySourceReader) -> None:
        self._dependencies = dependency_reader

    def build_write_prompt(self, spec: FileSpec, context: GenerationContext, current_code: str | None) -> str:
        sections = [
            f"PRODUCT REQUEST: {context.product_request}",
            f"CURRENT PHASE: {context.phase.name} - {context.phase.goal}",
            f"FEATURES IN SCOPE:\n{describe_for_prompt(context.catalog, context.phase.modules or None)}",
            f"EXISTING PROJECT SYMBOLS (import exactly these names):\n{context.project_symbols or '(none yet)'}",
        ]

        dependency_sources = self._dependencies.read(spec.depends_on)
        if dependency_sources:
            sections.append(f"SOURCE OF FILES THIS FILE DEPENDS ON:\n{dependency_sources}")

        if current_code:
            sections.append(f"CURRENT CONTENT OF THE FILE (modify it, keep what still applies):\n```python\n{current_code}\n```")

        sections.append(f"FILE TO WRITE\nPATH: {spec.path}\nKIND: {spec.kind}\nACTION: {spec.action}\nPURPOSE: {spec.purpose}")
        return "\n\n".join(sections)

    def build_repair_prompt(self, spec: FileSpec, context: GenerationContext, code: str, problem: str) -> str:
        return (
            f"FILE: {spec.path}\nPURPOSE: {spec.purpose}\n\n"
            f"EXISTING PROJECT SYMBOLS:\n{context.project_symbols}\n\n"
            f"CURRENT CODE:\n```python\n{code}\n```\n\n"
            f"PROBLEM TO FIX:\n{problem}"
        )
