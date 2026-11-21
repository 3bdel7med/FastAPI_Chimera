import asyncio
import json

import httpx
import pytest

from fast_chimera.config import Settings
from fast_chimera.core.exceptions import LlmAPIError
from fast_chimera.llm.gemini_client import GeminiClient
from fast_chimera.llm.retry import RetryPolicy


def make_client(handler, attempts=4):
    settings = Settings(gemini_api_key="SECRET-KEY", _env_file=None)
    policy = RetryPolicy(max_attempts=attempts, base_delay=0)

    async def no_sleep(seconds):
        return None

    return GeminiClient(settings, transport=httpx.MockTransport(handler), retry_policy=policy, sleep=no_sleep)


def ok(text="hello"):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]})


def test_key_is_sent_in_header_not_url_and_payload_is_well_formed():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return ok()

    text = asyncio.run(make_client(handler).generate_text("hi", "be brief", json_mode=True))
    assert text == "hello"
    assert "SECRET-KEY" not in seen["url"] and seen["key"] == "SECRET-KEY"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_retries_on_429_and_5xx_then_succeeds():
    responses = iter([httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(503), ok("done")])
    assert asyncio.run(make_client(lambda r: next(responses)).generate_text("x")) == "done"


def test_gives_up_after_configured_attempts_and_does_not_retry_client_errors():
    calls = []

    def always_500(request):
        calls.append(1)
        return httpx.Response(500, json={"error": {"message": "boom"}})

    with pytest.raises(LlmAPIError, match="boom"):
        asyncio.run(make_client(always_500, attempts=3).generate_text("x"))
    assert len(calls) == 3

    calls.clear()

    def bad_request(request):
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad key"}})

    with pytest.raises(LlmAPIError, match="bad key"):
        asyncio.run(make_client(bad_request).generate_text("x"))
    assert len(calls) == 1


def test_blocked_empty_and_truncated_responses_raise_clear_errors():
    for payload, message in [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "no candidates"),
        ({"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}, "empty response"),
        ({"candidates": [{"content": {"parts": [{"text": "x"}]}, "finishReason": "MAX_TOKENS"}]}, "truncated"),
    ]:
        with pytest.raises(LlmAPIError, match=message):
            asyncio.run(make_client(lambda r, p=payload: httpx.Response(200, json=p)).generate_text("x"))
