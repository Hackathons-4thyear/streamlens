"""The Gemini vision provider.

Uses the google-genai SDK with structured output: the model is handed a response
schema and returns JSON that already matches it, so we never parse prose. The
codes it returns are still validated against questions.json afterwards - a schema
guarantees shape, not truth.

Three things this file is careful about:

1. **Timeout.** The SDK's own `HttpOptions.timeout` has a history of being
   ignored (it has passed `timeout=None` through to httpx), so the SDK timeout is
   set *and* the whole call is wrapped in `asyncio.wait_for`. A citizen standing
   in the rain does not wait indefinitely for a model.
2. **One retry.** Transient transport failures are retried once. Authentication
   failures and malformed output are not - retrying those just doubles the wait
   before the same error.
3. **Async.** Uses `client.aio` so a slow model does not block the event loop.

The SDK is imported lazily so the app and its tests run without it installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path

from pydantic import BaseModel, Field

from .base import (
    AssessContext,
    ImageInput,
    ProviderError,
    ProviderResult,
    RawSuggestion,
    Usage,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def prompt_version() -> str:
    """The prompt the server is configured to use, e.g. 'assess_v1'."""
    from ..config import get_settings  # noqa: PLC0415 - avoids a circular import

    return get_settings().assess_prompt


def prompt_path(version: str | None = None) -> Path:
    return PROMPTS_DIR / f"{version or prompt_version()}.md"


# Kept as a module attribute so existing imports keep working; it reflects the
# configured prompt at import time.
PROMPT_VERSION = prompt_version()
PROMPT_PATH = prompt_path()

# Substrings that mark a failure as permanent. Retrying these is pointless.
_PERMANENT_MARKERS = (
    "api key",
    "api_key",
    "unauthenticated",
    "permission denied",
    "403",
    "401",
    "invalid argument",
    "not found",
    "404",
)


class _Suggestion(BaseModel):
    """The shape we require back from the model.

    `observation` is a thinking aid introduced in assess_v2: naming what is
    visible BEFORE choosing a code makes the answer follow the evidence rather
    than the reason rationalising a decision already made. It is not shown to
    the citizen. Optional, so assess_v1 still validates.
    """

    question_id: str = Field(description="Exact question id from the list.")
    observation: str = Field(
        default="",
        description="What is visible, as a short clause with no conclusion in it.",
    )
    codes: list[str] = Field(description="Exact answer codes. One for choose-ONE questions.")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(description="One short sentence for the volunteer, max 25 words.")


class _Response(BaseModel):
    suggestions: list[_Suggestion]
    note: str = ""


def load_prompt(version: str | None = None) -> str:
    """Read the prompt from disk at call time, so editing it needs no restart."""
    path = prompt_path(version)
    if not path.exists():
        raise ProviderError(f"no prompt file at {path}", "other")
    return path.read_text(encoding="utf-8")


def render_prompt(context: AssessContext, version: str | None = None) -> str:
    return (
        load_prompt(version)
        .replace("{{SITE_NAME}}", context.site_name or "unknown")
        .replace("{{CITY}}", context.city or "unknown")
        .replace("{{COUNTRY}}", context.country or "unknown")
        .replace("{{CATALOGUE}}", context.catalogue)
    )


def classify_failure(error: Exception) -> str:
    """Map an SDK exception onto a ProviderError kind."""
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    text = str(error).lower()
    if any(marker in text for marker in _PERMANENT_MARKERS):
        return "auth" if ("key" in text or "auth" in text or "permission" in text) else "other"
    if "timeout" in text or "timed out" in text or "deadline" in text:
        return "timeout"
    return "transport"


def is_retryable(kind: str) -> bool:
    """Retry only what a second attempt could plausibly fix."""
    return kind in {"timeout", "transport"}


class GeminiProvider:
    name = "gemini"
    is_mock = False

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 20.0,
        retries: int = 1,
        backoff_base_s: float = 0.6,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiProvider needs an API key")
        self.model = model
        self.timeout_s = timeout_s
        self.retries = max(0, retries)
        self.backoff_base_s = backoff_base_s
        self._api_key = api_key
        self._client = None

    def backoff_for(self, attempt: int) -> float:
        """Exponential backoff with jitter, in seconds, before `attempt` + 1.

        Retrying an overloaded model instantly just adds to the overload, and
        503 'high demand' is the failure this is most likely to meet.
        """
        if self.backoff_base_s <= 0:
            return 0.0
        return self.backoff_base_s * (2 ** (attempt - 1)) * (0.7 + random.random() * 0.6)

    # --- SDK plumbing -------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai  # noqa: PLC0415 - deliberately lazy
                from google.genai import types  # noqa: PLC0415
            except ImportError as exc:  # pragma: no cover - depends on env
                raise ProviderError(
                    "google-genai is not installed. Run "
                    "'pip install -r api/requirements.txt', or set AI_PROVIDER=mock.",
                    "other",
                ) from exc
            self._client = genai.Client(
                api_key=self._api_key,
                # Documented in milliseconds. Belt to the asyncio braces below.
                http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
            )
        return self._client

    def _build_parts(self, images: list[ImageInput], context: AssessContext) -> list:
        from google.genai import types  # noqa: PLC0415

        parts: list = [render_prompt(context)]
        for image in images:
            parts.append(f"This is the {image.role} photograph.")
            parts.append(types.Part.from_bytes(data=image.data, mime_type=image.mime_type))
        return parts

    async def _call_once(self, images: list[ImageInput], context: AssessContext):
        from google.genai import types  # noqa: PLC0415

        client = self._get_client()
        return await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self.model,
                contents=self._build_parts(images, context),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_Response,
                    temperature=0.2,
                    # We pass no tools, and the SDK warns about automatic
                    # function calling being on by default. Turn it off so the
                    # model has exactly one job: fill in the schema.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            ),
            timeout=self.timeout_s,
        )

    # --- provider interface -------------------------------------------------

    async def suggest(
        self, images: list[ImageInput], context: AssessContext
    ) -> ProviderResult:
        attempts = self.retries + 1
        last: ProviderError | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._call_once(images, context)
            except Exception as exc:  # noqa: BLE001 - the SDK raises many types
                kind = classify_failure(exc)
                last = ProviderError(str(exc) or exc.__class__.__name__, kind)
                if attempt < attempts and is_retryable(kind):
                    delay = self.backoff_for(attempt)
                    logger.warning(
                        "Gemini attempt %d/%d failed (%s); retrying in %.1fs.",
                        attempt, attempts, kind, delay,
                    )
                    if delay:
                        await asyncio.sleep(delay)
                    continue
                raise last from exc

            return self._to_result(response)

        raise last or ProviderError("Gemini produced no result", "other")

    def _to_result(self, response) -> ProviderResult:
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            text = getattr(response, "text", "") or ""
            try:
                parsed = _Response.model_validate(json.loads(text))
            except Exception as exc:  # noqa: BLE001 - a bad body is a provider failure
                raise ProviderError(
                    f"the model's answer could not be read: {exc}", "bad_output"
                ) from exc

        return ProviderResult(
            suggestions=[
                RawSuggestion(
                    question_id=s.question_id,
                    codes=list(s.codes),
                    confidence=float(s.confidence),
                    reason=s.reason,
                )
                for s in parsed.suggestions
            ],
            note=parsed.note or "",
            usage=_usage_of(response),
        )


def _usage_of(response) -> Usage:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return Usage()

    def count(name: str) -> int:
        return int(getattr(meta, name, 0) or 0)

    return Usage(
        prompt_tokens=count("prompt_token_count"),
        output_tokens=count("candidates_token_count"),
        thought_tokens=count("thoughts_token_count"),
        total_tokens=count("total_token_count"),
    )
