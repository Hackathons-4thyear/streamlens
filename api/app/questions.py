"""The question catalogue, loaded from data/questions.json.

This module is the single authority on which answer codes exist. Every AI
suggestion is checked against it before it can reach a citizen, so a model that
invents a code cannot put that code on screen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR

QUESTIONS_PATH = DATA_DIR / "questions.json"

# The answer that means "I could not tell". The AI is told to use it instead of
# guessing, and it is always a valid citizen answer.
UNKNOWN_CODE = "NS"


@dataclass(frozen=True)
class Question:
    id: str
    section: str
    type: str  # "single" | "multi"
    ai_suggestable: bool
    codes: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def is_multi(self) -> bool:
        return self.type == "multi"

    def allows(self, code: str) -> bool:
        return code in self.codes


class QuestionSet:
    """Loaded question catalogue with lookup and validation helpers."""

    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.questions: dict[str, Question] = {}
        for raw in doc.get("questions", []):
            question = Question(
                id=raw["id"],
                section=raw["section"],
                type=raw.get("type", "single"),
                ai_suggestable=bool(raw.get("ai_suggestable", True)),
                codes=tuple(o["code"] for o in raw.get("options", [])),
                raw=raw,
            )
            self.questions[question.id] = question

    # --- lookup ------------------------------------------------------------

    def get(self, question_id: str) -> Question | None:
        return self.questions.get(question_id)

    @property
    def languages(self) -> list[str]:
        return list(self.doc.get("languages", ["en"]))

    @property
    def suggestable(self) -> list[Question]:
        return [q for q in self.questions.values() if q.ai_suggestable]

    # --- validation --------------------------------------------------------

    def validate(self, question_id: str, code: str) -> tuple[bool, str]:
        """Check one answer. Returns (ok, reason-if-not)."""
        question = self.get(question_id)
        if question is None:
            return False, f"unknown question id '{question_id}'"
        if not question.allows(code):
            return False, (
                f"code '{code}' is not an option of '{question_id}' "
                f"(allowed: {', '.join(question.codes)})"
            )
        return True, ""

    def validate_answer(self, question_id: str, codes: list[str]) -> tuple[bool, str]:
        """Check a citizen answer: one code for single, one-or-more for multi."""
        question = self.get(question_id)
        if question is None:
            return False, f"unknown question id '{question_id}'"
        if not codes:
            return False, f"no answer given for '{question_id}'"
        if not question.is_multi and len(codes) > 1:
            return False, f"'{question_id}' accepts a single answer, got {len(codes)}"
        for code in codes:
            ok, reason = self.validate(question_id, code)
            if not ok:
                return False, reason
        return True, ""

    # --- localisation ------------------------------------------------------

    def localized(self, lang: str) -> dict[str, Any]:
        """Return the catalogue with every string resolved to `lang`.

        Missing translations fall back to English, and the response says which
        language was actually served so the UI can be honest about it.
        """
        lang = (lang or "en").lower()
        known = self.languages
        served = lang if lang in known else "en"

        missing: set[str] = set()

        def pick(value: Any) -> Any:
            if isinstance(value, dict) and ("en" in value or served in value):
                if served in value:
                    return value[served]
                missing.add("string")
                return value.get("en", "")
            if isinstance(value, dict):
                return {k: pick(v) for k, v in value.items()}
            if isinstance(value, list):
                return [pick(v) for v in value]
            return value

        doc = {k: v for k, v in self.doc.items() if k not in {"questions", "sections", "glossary"}}
        doc["questions"] = [pick(q) for q in self.doc.get("questions", [])]
        doc["sections"] = [pick(s) for s in self.doc.get("sections", [])]
        doc["glossary"] = {k: pick(v) for k, v in self.doc.get("glossary", {}).items()}
        doc["lang"] = served
        doc["lang_requested"] = lang
        doc["lang_complete"] = served == "en" or not missing
        doc["lang_note"] = (
            "English is complete. Other languages are our own translations and fall back "
            "to English where a string is missing."
        )
        return doc

    # --- prompt support ----------------------------------------------------

    def catalogue_for_prompt(self) -> str:
        """A compact, English listing of the suggestable questions for the model."""
        lines: list[str] = []
        for question in sorted(self.suggestable, key=lambda q: q.raw.get("order", 0)):
            raw = question.raw
            label = raw["label"].get("en", question.id)
            kind = "choose ALL that apply" if question.is_multi else "choose ONE"
            lines.append(f"- {question.id} ({kind}): {label}")
            lines.append(f"    what it means: {raw['explain'].get('en', '')}")
            for option in raw.get("options", []):
                lines.append(
                    f"    {option['code']} = {option['label'].get('en', '')}"
                    f" -- {option['explain'].get('en', '')}"
                )
        return "\n".join(lines)


def load_questions(path: Path | None = None) -> QuestionSet:
    target = path or QUESTIONS_PATH
    with target.open(encoding="utf-8") as fh:
        return QuestionSet(json.load(fh))


@lru_cache
def get_questions() -> QuestionSet:
    return load_questions()
