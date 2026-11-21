"""Responsibility: decide WHEN to retry and HOW LONG to wait. Knows nothing about HTTP clients."""

from __future__ import annotations

import random
from dataclasses import dataclass

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
MAX_RETRY_AFTER = 60.0


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 1.0
    max_delay: float = 30.0

    def is_retryable(self, status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS

    def delay_before_next_attempt(self, attempt: int, retry_after: float | None = None) -> float:
        """Exponential backoff with a little jitter; honours the server's Retry-After header."""
        if retry_after is not None:
            return min(retry_after, MAX_RETRY_AFTER)
        delay = min(self.base_delay * 2 ** (attempt - 1), self.max_delay)
        return delay * (1 + random.random() * 0.25)
