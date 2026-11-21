"""Responsibility: turn a ProjectSummary into the compact "symbol index" that goes into prompts,
so the model imports names that really exist."""

from __future__ import annotations

from fast_chimera.analysis.models import ModuleInfo, ProjectSummary


def format_symbol_index(summary: ProjectSummary, max_chars: int = 16000) -> str:
    modules = [module for module in summary.modules if not module.path.startswith("tests/")]
    blocks: list[str] = []
    used_chars = 0

    for position, module in enumerate(modules):
        block = _format_module(module)
        if block is None:
            continue
        if used_chars + len(block) > max_chars:
            blocks.append(f"... {len(modules) - position} more modules omitted for length")
            break
        blocks.append(block)
        used_chars += len(block)
    return "\n".join(blocks)


def _format_module(module: ModuleInfo) -> str | None:
    lines = [module.path]
    for class_info in module.classes:
        bases = f"({', '.join(class_info.bases)})" if class_info.bases else ""
        fields = f": {', '.join(class_info.fields)}" if class_info.fields else ""
        lines.append(f"  class {class_info.name}{bases}{fields}")
    lines += [f"  {signature}" for signature in module.functions]
    lines += [f"  router {router}" for router in module.routers]
    lines += [f"    {r.method} {r.path} -> {r.function}" for r in module.routes]

    has_content = len(lines) > 1
    return "\n".join(lines) if has_content else None
