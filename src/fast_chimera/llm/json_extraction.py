"""Responsibility: pull JSON or source code out of a free-form model answer."""

from __future__ import annotations

import json
import re
from typing import Any

_CODE_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*[ \t]*\n(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse JSON even when the model wrapped it in a code fence or added prose around it."""
    stripped = text.strip()
    candidates = [stripped]
    candidates += [block.strip() for block in _CODE_FENCE.findall(stripped)]

    first_brace, last_brace = stripped.find("{"), stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(stripped[first_brace : last_brace + 1])

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as error:
            last_error = error
    raise last_error or json.JSONDecodeError("empty answer", text, 0)


def extract_code(text: str) -> str:
    """The largest fenced code block, or the whole answer when there is no fence."""
    blocks = _CODE_FENCE.findall(text)
    if not blocks:
        return text.strip()
    return max(blocks, key=len).strip()
