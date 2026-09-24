"""The Gemini provider's retry, timeout and failure-classification logic.

No network: `_call_once` is replaced, so these test our control flow around the
SDK rather than the SDK itself.
"""

from __future__ import annotations

import asyncio

import pytest

from app.ai.base import AssessContext, ImageInput, ProviderError, Usage
from app.ai.gemini import GeminiProvider, classify_failure, is_retryable, render_prompt


@pytest.fixture
def provider() -> GeminiProvider:
    return GeminiProvider("test-key", "gemini-2.5-flash", timeout_s=0.2, retries=1)


def _images() -> list[ImageInput]:
    return [ImageInput(role="upstream", data=b"not-really-a-jpeg")]


def _context() -> AssessContext:
    return AssessContext(site_name="Test", city="Coimbra", catalogue="- channelType")


# --------------------------------------------------------------------------
# Failure classification
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (asyncio.TimeoutError(), "timeout"),
        (TimeoutError(), "timeout"),
        (RuntimeError("deadline exceeded"), "timeout"),
        (RuntimeError("Connection reset by peer"), "transport"),
        (RuntimeError("API key not valid"), "auth"),
        (RuntimeError("403 permission denied"), "auth"),
        (RuntimeError("something odd"), "transport"),
    ],
)
def test_failures_are_classified(error, expected):
    assert classify_failure(error) == expected


def test_only_transient_failures_are_retried():
    assert is_retryable("timeout") is True
    assert is_retryable("transport") is True
    # Retrying a bad key just doubles the wait before the same error.
    assert is_retryable("auth") is False
    assert is_retryable("bad_output") is False


# --------------------------------------------------------------------------
# Retry behaviour
# --------------------------------------------------------------------------

async def test_a_transient_failure_is_retried_exactly_once(provider, monkeypatch):
    calls = {"n": 0}

    async def fail(images, context):
        calls["n"] += 1
        raise RuntimeError("Connection reset by peer")

    monkeypatch.setattr(provider, "_call_once", fail)

    with pytest.raises(ProviderError) as caught:
        await provider.suggest(_images(), _context())

    assert calls["n"] == 2, "one attempt plus one retry"
    assert caught.value.kind == "transport"


async def test_a_retry_that_succeeds_returns_the_result(provider, monkeypatch):
    calls = {"n": 0}

    class _Parsed:
        suggestions: list = []
        note = "second time lucky"

    class _Response:
        parsed = _Parsed()
        usage_metadata = None

    async def flaky(images, context):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Connection reset by peer")
        return _Response()

    monkeypatch.setattr(provider, "_call_once", flaky)

    result = await provider.suggest(_images(), _context())
    assert calls["n"] == 2
    assert result.note == "second time lucky"


async def test_an_auth_failure_is_not_retried(provider, monkeypatch):
    calls = {"n": 0}

    async def fail(images, context):
        calls["n"] += 1
        raise RuntimeError("API key not valid")

    monkeypatch.setattr(provider, "_call_once", fail)

    with pytest.raises(ProviderError) as caught:
        await provider.suggest(_images(), _context())

    assert calls["n"] == 1, "a bad key is not worth a second attempt"
    assert caught.value.kind == "auth"


async def test_retries_can_be_switched_off(monkeypatch):
    provider = GeminiProvider("k", "m", timeout_s=0.2, retries=0)
    calls = {"n": 0}

    async def fail(images, context):
        calls["n"] += 1
        raise RuntimeError("Connection reset by peer")

    monkeypatch.setattr(provider, "_call_once", fail)

    with pytest.raises(ProviderError):
        await provider.suggest(_images(), _context())
    assert calls["n"] == 1


# --------------------------------------------------------------------------
# Timeout
# --------------------------------------------------------------------------

async def test_a_hanging_call_is_cut_off_at_the_timeout(monkeypatch):
    """The SDK's own timeout has a history of being ignored, so the provider
    enforces one itself. A citizen in the rain does not wait forever."""
    provider = GeminiProvider("k", "m", timeout_s=0.05, retries=0)

    async def hang(*args, **kwargs):
        await asyncio.sleep(10)

    class _Models:
        generate_content = staticmethod(hang)

    class _Aio:
        models = _Models()

    class _Client:
        aio = _Aio()

    monkeypatch.setattr(provider, "_get_client", lambda: _Client())
    monkeypatch.setattr(provider, "_build_parts", lambda images, context: ["x"])
    monkeypatch.setattr(
        "app.ai.gemini.GeminiProvider._call_once",
        GeminiProvider._call_once,
    )

    started = asyncio.get_event_loop().time()
    with pytest.raises(ProviderError) as caught:
        await provider.suggest(_images(), _context())

    assert caught.value.kind == "timeout"
    assert asyncio.get_event_loop().time() - started < 2, "it did not wait for the call"


# --------------------------------------------------------------------------
# Output handling
# --------------------------------------------------------------------------

async def test_unreadable_output_is_a_bad_output_failure(provider, monkeypatch):
    class _Response:
        parsed = None
        text = "I'm afraid I can't do that."
        usage_metadata = None

    async def ok(images, context):
        return _Response()

    monkeypatch.setattr(provider, "_call_once", ok)

    with pytest.raises(ProviderError) as caught:
        await provider.suggest(_images(), _context())
    assert caught.value.kind == "bad_output"


async def test_token_usage_is_captured_for_cost_accounting(provider, monkeypatch):
    class _Meta:
        prompt_token_count = 1500
        candidates_token_count = 300
        thoughts_token_count = 120
        total_token_count = 1920

    class _Parsed:
        suggestions: list = []
        note = ""

    class _Response:
        parsed = _Parsed()
        usage_metadata = _Meta()

    async def ok(images, context):
        return _Response()

    monkeypatch.setattr(provider, "_call_once", ok)

    result = await provider.suggest(_images(), _context())
    assert result.usage == Usage(1500, 300, 120, 1920)
    # Thinking tokens bill as output, so cost must include them.
    assert result.usage.billed_output_tokens == 420


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

def test_the_prompt_is_rendered_with_the_site_and_catalogue():
    rendered = render_prompt(
        AssessContext(site_name="Vale das Flores", city="Coimbra",
                      country="Portugal", catalogue="- channelType (choose ONE)")
    )
    assert "Vale das Flores" in rendered
    assert "Coimbra" in rendered
    assert "- channelType (choose ONE)" in rendered
    assert "{{" not in rendered, "every placeholder should be filled"


def test_the_prompt_forbids_rating_and_encourages_not_sure():
    rendered = render_prompt(AssessContext(catalogue=""))
    assert "Never propose an overall rating" in rendered
    assert "NS" in rendered
