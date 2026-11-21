"""Responsibility: a stable hash of a fingerprint's STRUCTURE (the timestamp is ignored),
used as an idempotency key: same project => same hash."""

from __future__ import annotations

import hashlib
import json

from fast_chimera.shift.schema import Fingerprint


def compute_content_hash(fingerprint: Fingerprint) -> str:
    data = fingerprint.model_dump(exclude={"generated_at", "content_sha256"}, exclude_none=True)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
