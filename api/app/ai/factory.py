"""Choose a vision provider from settings.

Falling back to the mock is always safe and always visible: the response carries
`is_mock`, and the UI shows a badge. Failing loudly to the citizen in a field
would be worse than a labelled demo provider.
"""

from __future__ import annotations

import logging

from ..config import Settings
from .base import VisionProvider
from .mock import MockProvider

logger = logging.getLogger(__name__)


def get_provider(settings: Settings) -> VisionProvider:
    if settings.use_gemini:
        try:
            from .gemini import GeminiProvider  # noqa: PLC0415 - avoids importing the SDK

            return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
        except Exception as exc:  # noqa: BLE001 - never break the flow over a provider
            logger.warning("Could not start the Gemini provider (%s); using the mock.", exc)
            return MockProvider()

    if settings.ai_provider.lower() == "gemini":
        logger.warning("AI_PROVIDER=gemini but GEMINI_API_KEY is empty; using the mock.")

    return MockProvider()
