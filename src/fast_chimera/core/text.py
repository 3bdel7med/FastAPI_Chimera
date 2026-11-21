from __future__ import annotations

import hashlib
import re


def slugify(value: str, max_length: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_length].strip("-")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tail(text: str, limit: int = 2000) -> str:
    return text if len(text) <= limit else "…" + text[-limit:]


def package_name(requirement: str) -> str:
    """'Stripe[extra]>=7' -> 'stripe' (normalized distribution name)."""
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    return match.group(0).lower().replace("_", "-") if match else ""
