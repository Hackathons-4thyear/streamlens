"""The provider-agnostic vision interface.

Everything above this line in the stack talks to `VisionProvider` and never to a
vendor SDK, so swapping Gemini for another model is a new file in this folder.

A provider's job is narrow: look at the photos, propose answers to the questions
it was given, and say how sure it is. It does not decide anything. Validation of
the codes it returns happens outside, in the router, against questions.json.

`suggest` is async because a real provider is a network call with a timeout, and
blocking the event loop for twenty seconds would stall every other request.
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
class Usage:
    """Token counts, for cost accounting in the evaluation harness.

    `thought_tokens` is separate because thinking models bill it as output but
    report it apart from the visible answer.
    """

    prompt_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    total_tokens: int = 0

    @property
    def billed_output_tokens(self) -> int:
        return self.output_tokens + self.thought_tokens


@dataclass
class ProviderResult:
    suggestions: list[RawSuggestion] = field(default_factory=list)
    # Free-text note from the provider, e.g. why it answered little.
    note: str = ""
    usage: Usage = field(default_factory=Usage)
    # The watercourse gate: False means the photo is not of a stream at all,
    # and no suggestion should be shown whatever else came back.
    is_watercourse: bool = True
    not_watercourse_reason: str = ""


class ProviderError(RuntimeError):
    """A provider could not produce a result.

    `kind` is one of "timeout", "transport", "auth", "bad_output" or "other",
    so the caller can say something specific without parsing a message.
    """

    def __init__(self, message: str, kind: str = "other") -> None:
        super().__init__(message)
        self.kind = kind


@runtime_checkable
class VisionProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    async def suggest(
        self, images: list[ImageInput], context: AssessContext
    ) -> ProviderResult:
        ...
