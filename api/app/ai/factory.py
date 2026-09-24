"""Choosing a provider, and failing loudly when the real one is unavailable.

The fallback policy, in one place:

- If Gemini is configured and works, its suggestions are used.
- If Gemini is configured and fails, the request still succeeds, using the mock
  provider so the citizen's visit is never lost - but the response is marked
  `degraded` with a reason, and the UI says "AI unavailable, answer manually".
  The mock badge shows as well, so nothing on screen claims to be a real model.
- A silent fallback would be the worst outcome: plausible-looking suggestions
  with nothing saying where they came from.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ..config import Settings
from .base import (
    AssessContext,
    ImageInput,
    ProviderError,
    ProviderResult,
    Usage,
    VisionProvider,
)
from .mock import MockProvider

logger = logging.getLogger(__name__)

# What to tell a citizen, per failure kind. Short, plain, and never technical.
DEGRADED_MESSAGES = {
    "timeout": "The AI took too long to answer.",
    "transport": "The AI could not be reached.",
    "auth": "The AI is not configured correctly on the server.",
    "bad_output": "The AI's answer could not be read.",
    "other": "The AI is unavailable.",
}


def get_provider(settings: Settings) -> VisionProvider:
    """The provider the settings ask for, or the mock when that is not possible."""
    if settings.use_gemini:
        try:
            from .gemini import GeminiProvider  # noqa: PLC0415 - avoids importing the SDK

            return GeminiProvider(
                settings.gemini_api_key,
                settings.gemini_model,
                timeout_s=settings.gemini_timeout_s,
                retries=settings.gemini_retries,
                backoff_base_s=settings.gemini_backoff_base_s,
            )
        except Exception as exc:  # noqa: BLE001 - never break the flow over a provider
            logger.warning("Could not start the Gemini provider (%s); using the mock.", exc)
            return MockProvider()

    if settings.ai_provider.lower() == "gemini":
        logger.warning("AI_PROVIDER=gemini but GEMINI_API_KEY is empty; using the mock.")

    return MockProvider()


@dataclass
class SuggestOutcome:
    """The result of asking for suggestions, plus how it went."""

    result: ProviderResult
    provider: str
    model: str
    is_mock: bool
    requested_provider: str
    degraded: bool = False
    degraded_reason: str = ""
    degraded_kind: str = ""
    attempts: int = 1
    latency_ms: int = 0
    usage: Usage = field(default_factory=Usage)


async def suggest_with_fallback(
    settings: Settings,
    images: list[ImageInput],
    context: AssessContext,
    provider: VisionProvider | None = None,
) -> SuggestOutcome:
    """Ask the configured provider, falling back to the mock, visibly."""
    provider = provider or get_provider(settings)
    requested = settings.ai_provider.lower()
    started = time.perf_counter()

    try:
        result = await provider.suggest(images, context)
    except Exception as exc:  # noqa: BLE001 - any provider failure lands here
        kind = getattr(exc, "kind", "other") if isinstance(exc, ProviderError) else "other"
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "Provider %s failed after %d ms (%s): %s", provider.name, elapsed, kind, exc
        )

        if provider.is_mock:
            # The mock has no network and no excuse. Let this one surface.
            raise

        fallback = MockProvider()
        fallback_result = await fallback.suggest(images, context)
        return SuggestOutcome(
            result=fallback_result,
            provider=fallback.name,
            model=fallback.model,
            is_mock=True,
            requested_provider=requested,
            degraded=True,
            degraded_reason=DEGRADED_MESSAGES.get(kind, DEGRADED_MESSAGES["other"]),
            degraded_kind=kind,
            attempts=getattr(provider, "retries", 0) + 1,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    return SuggestOutcome(
        result=result,
        provider=provider.name,
        model=provider.model,
        is_mock=provider.is_mock,
        requested_provider=requested,
        latency_ms=int((time.perf_counter() - started) * 1000),
        usage=result.usage,
    )
