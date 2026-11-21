"""Responsibility: read the source of the files a new file depends on, within a size budget."""

from __future__ import annotations

from pathlib import Path

MAX_CHARS_PER_FILE = 6000
MAX_CHARS_TOTAL = 24000


class DependencySourceReader:
    def __init__(self, project_root: Path) -> None:
        self._root = Path(project_root)

    def read(self, dependency_paths: list[str]) -> str:
        blocks: list[str] = []
        total_chars = 0
        for relative_path in dependency_paths:
            file_path = self._root / relative_path
            if not file_path.is_file():
                continue
            source = file_path.read_text(encoding="utf-8")[:MAX_CHARS_PER_FILE]
            if total_chars + len(source) > MAX_CHARS_TOTAL:
                break
            total_chars += len(source)
            blocks.append(f"### {relative_path}\n```python\n{source}\n```")
        return "\n\n".join(blocks)
