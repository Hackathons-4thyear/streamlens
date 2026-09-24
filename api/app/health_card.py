"""The stream health card: what citizens have actually reported at one site.

Built **only** from citizen-confirmed answers. An AI suggestion that nobody
accepted is not in the database as an answer and never reaches this file.

The section statuses are an **indicator view, not a validated ecological
index**. They are derived by a rule anyone can check: a section is graded by how
many of its answered questions match a known problem in the measures catalogue.
That is a useful summary for a citizen and a starting point for a municipality.
It is not WFD status, it is not an ecological quality ratio, and the payload
says so in a field the UI is required to display.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .measures import MeasureSet
from .questions import QuestionSet

INDICATOR_DISCLAIMER = (
    "Indicator view, not a validated ecological index. These sections summarise "
    "what visitors reported; they are not a legal or scientific classification of "
    "this stream."
)

# A section is Poor when more than this share of its answered questions match a
# known problem, Moderate when any do, Good when none do.
POOR_RATIO = 0.5


@dataclass
class SectionStatus:
    section_id: str
    label: str
    status: str  # "GOOD" | "MODERATE" | "POOR" | "UNKNOWN"
    answered: int
    total: int
    problem_hits: list[dict] = field(default_factory=list)
    reason: str = ""


@dataclass
class HealthCard:
    site_id: str
    site_name: str
    city: str
    visits: int
    last_visit: datetime | None
    first_visit: datetime | None
    overall_history: list[dict] = field(default_factory=list)
    latest_overall: str | None = None
    sections: list[SectionStatus] = field(default_factory=list)
    problems: list[dict] = field(default_factory=list)
    completeness: float = 0.0
    completeness_label: str = ""
    answered_questions: int = 0
    total_questions: int = 0
    emotions: dict[str, float] = field(default_factory=dict)
    synthetic_included: bool = True
    synthetic_count: int = 0
    real_count: int = 0
    disclaimer: str = INDICATOR_DISCLAIMER


def build(
    site: dict[str, Any],
    observations: list[dict],
    questions: QuestionSet,
    measures: MeasureSet,
) -> HealthCard:
    """Aggregate a site's observations into a card.

    `observations` is a list of dicts with keys: id, overall, recorded_at,
    synthetic, emotions, answers -> [{question_id, codes}].
    """
    visits = len(observations)
    ordered = sorted(observations, key=lambda o: o["recorded_at"])

    # Latest confirmed codes per question, plus everything ever reported.
    latest_by_question: dict[str, set[str]] = {}
    ever_by_question: dict[str, set[str]] = defaultdict(set)
    for observation in ordered:
        for answer in observation.get("answers", []):
            codes = set(answer.get("codes") or [])
            if not codes:
                continue
            latest_by_question[answer["question_id"]] = codes
            ever_by_question[answer["question_id"]] |= codes

    problems = measures.problems_for_answers(latest_by_question)
    problem_questions: dict[str, list[dict]] = defaultdict(list)
    for problem in problems:
        for hit in problem["matched"]:
            problem_questions[hit["question_id"]].append({
                "problem_id": problem["id"],
                "problem_name": problem["name"],
                "codes": hit["codes"],
            })

    sections: list[SectionStatus] = []
    for section in questions.doc.get("sections", []):
        section_id = section["id"]
        if section_id == "verdict":
            continue
        in_section = [
            q for q in questions.questions.values() if q.section == section_id
        ]
        answered = [q for q in in_section if q.id in latest_by_question]
        hits = [h for q in answered for h in problem_questions.get(q.id, [])]

        if not answered:
            status, reason = "UNKNOWN", "Nobody has answered these questions here yet."
        else:
            ratio = len({h["problem_name"] for h in hits}) / len(answered) if hits else 0
            if not hits:
                status = "GOOD"
                reason = (f"{len(answered)} of {len(in_section)} questions answered, "
                          "none matching a known problem.")
            elif ratio > POOR_RATIO:
                status = "POOR"
                reason = (f"{len(hits)} of {len(answered)} answered questions match a "
                          "known problem.")
            else:
                status = "MODERATE"
                reason = (f"{len(hits)} of {len(answered)} answered questions match a "
                          "known problem.")

        sections.append(SectionStatus(
            section_id=section_id,
            label=section["label"].get("en", section_id)
            if isinstance(section["label"], dict) else section["label"],
            status=status,
            answered=len(answered),
            total=len(in_section),
            problem_hits=hits,
            reason=reason,
        ))

    history = [
        {
            "observation_id": o["id"],
            "overall": o["overall"],
            "recorded_at": o["recorded_at"].isoformat()
            if isinstance(o["recorded_at"], datetime) else o["recorded_at"],
            "synthetic": bool(o.get("synthetic")),
        }
        for o in ordered
    ]

    total_questions = len([q for q in questions.questions.values() if q.id != "overall"])
    answered_questions = len(latest_by_question)
    completeness = answered_questions / total_questions if total_questions else 0.0
    if completeness >= 0.8:
        label = "Well covered"
    elif completeness >= 0.4:
        label = "Partly covered"
    elif completeness > 0:
        label = "Thin - more visits needed"
    else:
        label = "No data yet"

    emotion_totals: dict[str, list[int]] = defaultdict(list)
    for observation in ordered:
        for name, level in (observation.get("emotions") or {}).items():
            emotion_totals[name].append(int(level))
    emotions = {
        name: round(sum(values) / len(values), 2)
        for name, values in emotion_totals.items() if values
    }

    synthetic_count = sum(1 for o in ordered if o.get("synthetic"))
    last = ordered[-1]["recorded_at"] if ordered else None
    first = ordered[0]["recorded_at"] if ordered else None

    return HealthCard(
        site_id=site.get("id", ""),
        site_name=site.get("name", ""),
        city=site.get("city", ""),
        visits=visits,
        last_visit=last if isinstance(last, datetime) else None,
        first_visit=first if isinstance(first, datetime) else None,
        overall_history=history,
        latest_overall=ordered[-1]["overall"] if ordered else None,
        sections=sections,
        problems=[
            {
                "id": p["id"],
                "name": p["name"],
                "why_it_matters": p["why_it_matters"],
                "matched": p["matched"],
                "detection_note": p.get("detection_note", ""),
            }
            for p in problems
        ],
        completeness=round(completeness, 3),
        completeness_label=label,
        answered_questions=answered_questions,
        total_questions=total_questions,
        emotions=emotions,
        synthetic_count=synthetic_count,
        real_count=visits - synthetic_count,
    )
