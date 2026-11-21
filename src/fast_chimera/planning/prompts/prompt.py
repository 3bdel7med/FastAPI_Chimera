from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """A system instruction plus the user message. Every system prompt starts with a [task:*] tag
    so logs (and test doubles) can tell the different calls apart."""

    system: str
    user: str
