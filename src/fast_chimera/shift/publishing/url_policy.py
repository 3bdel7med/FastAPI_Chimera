"""Responsibility: decide whether a server URL is safe to send a fingerprint (and a token) to."""

from __future__ import annotations

from urllib.parse import urlparse

from fast_chimera.core.exceptions import ShiftConfigError

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_server_url(url: str, *, allow_insecure: bool = False) -> str:
    parsed = urlparse(url.strip())

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ShiftConfigError("SHIFT_SERVER_URL must be an absolute http(s) URL, e.g. https://platform.example.com/api/shift")
    if parsed.username or parsed.password:
        raise ShiftConfigError("Do not put credentials in SHIFT_SERVER_URL; use SHIFT_API_TOKEN instead.")

    is_plain_http = parsed.scheme == "http"
    if is_plain_http and parsed.hostname not in LOCAL_HOSTS and not allow_insecure:
        raise ShiftConfigError(
            "SHIFT_SERVER_URL must use https (plain http is only allowed for localhost). Set SHIFT_ALLOW_INSECURE=true to override."
        )
    return url.strip()


def display_url(url: str) -> str:
    """The URL without query string or fragment: safe to print, because those can carry tokens."""
    return urlparse(url)._replace(query="", fragment="").geturl()
