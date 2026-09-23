"""The provider-agnostic vision interface.

Everything above this line in the stack talks to `VisionProvider` and never to a
vendor SDK, so swapping Gemini for another model is a new file in this folder.

A provider's job is narrow: look at the photos, propose answers to the questions
it was given, and say how sure it is. It does not decide anything. Validation of
the codes it returns happens outside, in the router, against questions.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ImageInput:
    """One prepared photo handed to a provider."""

    role: str  # "upstream" | "downstream"
    data: bytes
    mime_type: str = "image/jpeg"


@dataclass
class AssessContext:
    """Everything the provider is allowed to know about the visit."""

    site_name: str = ""
    city: str = ""
    country: str = ""
    catalogue: str = ""  # the question listing, already rendered for the prompt


@dataclass
class RawSuggestion:
    """A provider's proposal, before validation."""

    question_id: str
    codes: list[str]
    confidence: float
    reason: str


@dataclass
class ProviderResult:
    suggestions: list[RawSuggestion] = field(default_factory=list)
    # Free-text note from the provider, e.g. why it answered little.
    note: str = ""


@runtime_checkable
class VisionProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    def suggest(self, images: list[ImageInput], context: AssessContext) -> ProviderResult:
        ...
