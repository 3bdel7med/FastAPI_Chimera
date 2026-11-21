"""Responsibility: decide what to do when a planned file may already exist on disk."""

from __future__ import annotations

from enum import Enum


class WriteDecision(Enum):
    WRITE_NEW = "write_new"
    OVERWRITE = "overwrite"
    SKIP_USER_FILE = "skip_user_file"


class OverwritePolicy:
    """A file is safe to replace when we wrote it ourselves, when the plan says MODIFY,
    or when the user passed --force. Anything else is the user's own work: leave it alone."""

    def __init__(self, force: bool = False) -> None:
        self._force = force

    def decide(self, *, file_exists: bool, written_by_us: bool, action: str) -> WriteDecision:
        if not file_exists:
            return WriteDecision.WRITE_NEW
        if self._force or written_by_us or action == "MODIFY":
            return WriteDecision.OVERWRITE
        return WriteDecision.SKIP_USER_FILE
