"""The Gemini vision provider.

Uses the google-genai SDK with structured output: the model is handed a response
schema and returns JSON that already matches it, so we never parse prose. The
codes it returns are still validated against questions.json afterwards - a schema
guarantees shape, not truth.

The SDK is imported lazily so the app and its tests run without it installed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from .base import AssessContext, ImageInput, ProviderResult, RawSuggestion

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "assess_v1.md"
PROMPT_VERSION = "assess_v1"


class _Suggestion(BaseModel):
    """The shape we require back from the model."""

    question_id: str = Field(description="Exact question id from the list.")
    codes: list[str] = Field(description="Exact answer codes. One for choose-ONE questions.")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(description="One short sentence for the volunteer, max 25 words.")


class _Response(BaseModel):
    suggestions: list[_Suggestion]
    note: str = ""


def load_prompt() -> str:
    """Read the prompt from disk at call time, so editing it needs no restart."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def render_prompt(context: AssessContext) -> str:
    return (
        load_prompt()
        .replace("{{SITE_NAME}}", context.site_name or "unknown")
        .replace("{{CITY}}", context.city or "unknown")
        .replace("{{COUNTRY}}", context.country or "unknown")
        .replace("{{CATALOGUE}}", context.catalogue)
    )


class GeminiProvider:
    name = "gemini"
    is_mock = False

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("GeminiProvider needs an API key")
        self.model = model
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai  # noqa: PLC0415 - deliberately lazy
            except ImportError as exc:  # pragma: no cover - depends on env
                raise RuntimeError(
                    "google-genai is not installed. Run "
                    "'pip install -r api/requirements.txt', or set AI_PROVIDER=mock."
                ) from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def suggest(self, images: list[ImageInput], context: AssessContext) -> ProviderResult:
        from google.genai import types  # noqa: PLC0415 - lazy with the client

        client = self._get_client()
        parts: list[object] = [render_prompt(context)]
        for image in images:
            parts.append(f"This is the {image.role} photograph.")
            parts.append(types.Part.from_bytes(data=image.data, mime_type=image.mime_type))

        response = client.models.generate_content(
            model=self.model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Response,
                temperature=0.2,
            ),
        )

        parsed = getattr(response, "parsed", None)
        if parsed is None:
            try:
                parsed = _Response.model_validate(json.loads(response.text))
            except Exception as exc:  # noqa: BLE001 - a bad body is a provider failure
                logger.warning("Gemini returned unparseable output: %s", exc)
                return ProviderResult(
                    suggestions=[],
                    note="The model's answer could not be read, so nothing was suggested.",
                )

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
        )
