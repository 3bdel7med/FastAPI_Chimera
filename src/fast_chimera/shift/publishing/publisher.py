"""Responsibility: POST the fingerprint to the server the user configured.

Contract:  POST <SHIFT_SERVER_URL>, JSON body = the fingerprint, optional `Authorization: Bearer <token>`,
           `Idempotency-Key` = the fingerprint's content hash. Any 2xx means success.
Redirects are NOT followed: they could leak the token or downgrade the connection to http."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from fast_chimera import __version__
from fast_chimera.core.exceptions import ShiftConfigError, ShiftError
from fast_chimera.shift.publishing.settings import ShiftSettings
from fast_chimera.shift.publishing.url_policy import display_url
from fast_chimera.shift.schema import Fingerprint

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_BACKOFF_SECONDS = 10


@dataclass(frozen=True)
class SendResult:
    status_code: int
    destination: str
    attempts: int
    remote_id: str | None = None


class ShiftPublisher:
    def __init__(
        self,
        settings: ShiftSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._sleep = sleep

    def send(self, fingerprint: Fingerprint, url_override: str | None = None) -> SendResult:
        url = self._settings.server_url(url_override)
        if not url:
            raise ShiftConfigError("No server configured: set SHIFT_SERVER_URL in your .env file (or pass --server).")

        destination = display_url(url)
        headers = self._build_headers(fingerprint)
        body = fingerprint.to_json(indent=None).encode("utf-8")
        attempts = max(1, self._settings.shift_retry_attempts)
        last_problem = "unknown error"

        with httpx.Client(timeout=self._settings.shift_timeout, transport=self._transport, follow_redirects=False) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = client.post(url, content=body, headers=headers)
                except httpx.TransportError as error:
                    last_problem = f"could not reach {destination}: {type(error).__name__}"
                else:
                    if response.is_success:
                        return SendResult(response.status_code, destination, attempt, _remote_id(response))
                    if response.is_redirect:
                        raise ShiftError(
                            f"{destination} redirected (HTTP {response.status_code}). Redirects are not followed; "
                            "set SHIFT_SERVER_URL to the final URL."
                        )
                    last_problem = f"server answered HTTP {response.status_code}: {_snippet(response)}"
                    if response.status_code not in RETRYABLE_STATUS:
                        raise ShiftError(f"The server rejected the fingerprint ({last_problem})")

                if attempt < attempts:
                    self._sleep(min(2 ** (attempt - 1), MAX_BACKOFF_SECONDS))

        raise ShiftError(f"Sending failed after {attempts} attempt(s): {last_problem}")

    def _build_headers(self, fingerprint: Fingerprint) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"fast-chimera/{__version__}",
            "Idempotency-Key": fingerprint.content_sha256,
            "X-FastChimera-Content-SHA256": fingerprint.content_sha256,
        }
        token = self._settings.shift_api_token
        if token:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        return headers


def _snippet(response: httpx.Response) -> str:
    return " ".join(response.text.split())[:200]


def _remote_id(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    value = data.get("id") if isinstance(data, dict) else None
    return str(value)[:80] if value is not None else None
