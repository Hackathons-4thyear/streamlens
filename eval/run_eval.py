"""Measure the assessment prompt against real photographs.

Runs every image in eval/photos/ through the configured provider, using exactly
the same preparation and validation path as the live API, and writes a report to
eval/reports/<prompt_version>.md plus the raw run as JSON beside it.

What it measures, per question and overall:

- **agreement** with your labels in eval/labels.csv (exact match on the code set)
- **unknown rate** - how often the model answered NS ("I'm not sure")
- **dropped rate** - suggestions thrown out by validation before a citizen
  could see them, which is the sharpest signal that a prompt is failing
- **calibration** - mean confidence when right against mean confidence when
  wrong. A model whose confidence is the same either way is not telling you
  anything, however accurate it is.
- **latency and approximate cost**

Labels are optional. With none filled in, everything except agreement and
calibration still works, which is enough to judge a prompt's honesty.

Usage:
    python eval/run_eval.py                  # all photos, configured provider
    python eval/run_eval.py --limit 5        # first five, for a cheap smoke test
    python eval/run_eval.py --site C1        # pretend the visit was to this site
    python eval/run_eval.py --label-suffix dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
PHOTOS_DIR = EVAL_DIR / "photos"
LABELS_PATH = EVAL_DIR / "labels.csv"
PRICING_PATH = EVAL_DIR / "pricing.json"
REPORTS_DIR = EVAL_DIR / "reports"

sys.path.insert(0, str(REPO_ROOT / "api"))

from app.ai.base import AssessContext, ImageInput  # noqa: E402
from app.ai.factory import suggest_with_fallback  # noqa: E402
from app.ai.gemini import prompt_version  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.imaging import prepare  # noqa: E402
from app.questions import get_questions  # noqa: E402
from app.routers.assess import validate_suggestions  # noqa: E402
from app.sites import get_sites  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
UNKNOWN_CODE = "NS"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

@dataclass
class PhotoRun:
    photo: str
    ok: bool = True
    error: str = ""
    latency_ms: int = 0
    degraded: bool = False
    degraded_reason: str = ""
    provider: str = ""
    model: str = ""
    is_mock: bool = True
    chips: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    photo_ok: bool = True
    photo_issues: list[str] = field(default_factory=list)


@dataclass
class QuestionStats:
    question_id: str
    suggested: int = 0
    unknown: int = 0
    dropped: int = 0
    labelled: int = 0
    correct: int = 0
    confidences_right: list[float] = field(default_factory=list)
    confidences_wrong: list[float] = field(default_factory=list)

    @property
    def agreement(self) -> float | None:
        return self.correct / self.labelled if self.labelled else None

    @property
    def unknown_rate(self) -> float | None:
        return self.unknown / self.suggested if self.suggested else None


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def find_photos(limit: int | None, directory: Path | None = None) -> list[Path]:
    folder = directory or PHOTOS_DIR
    if not folder.exists():
        return []
    photos = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    return photos[:limit] if limit else photos


def read_labels(path: Path | None = None) -> dict[tuple[str, str], set[str]]:
    """(photo, question_id) -> the set of codes you said were right."""
    target = path or LABELS_PATH
    if not target.exists():
        return {}
    labels: dict[tuple[str, str], set[str]] = {}
    with target.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("code") or "").strip()
            if not raw:
                continue
            codes = {c.strip() for c in raw.replace(",", ";").split(";") if c.strip()}
            if codes:
                labels[(row["photo"], row["question_id"])] = codes
    return labels


def read_usable(path: Path | None = None) -> dict[str, bool]:
    """Which photographs the labeller judged to show a watercourse at all."""
    target = path or LABELS_PATH
    if not target.exists():
        return {}
    usable: dict[str, bool] = {}
    with target.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            flag = (row.get("photo_usable") or "yes").strip().lower()
            usable[row["photo"]] = flag != "no"
    return usable


def load_pricing() -> dict:
    with PRICING_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def price_for(pricing: dict, model: str) -> dict:
    table = pricing["per_million_tokens"]
    return table.get(model, table["_default"])


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------

async def run_photo(path: Path, site: dict, settings, questions) -> PhotoRun:
    run = PhotoRun(photo=path.name)
    try:
        prepared = prepare(
            path.read_bytes(),
            "upstream",
            max_px=settings.max_image_px,
            blur_threshold=settings.blur_threshold,
            dark_threshold=settings.dark_threshold,
            bright_threshold=settings.bright_threshold,
        )
    except ValueError as exc:
        run.ok = False
        run.error = str(exc)
        return run

    run.photo_ok = prepared.ok
    run.photo_issues = [issue.code for issue in prepared.issues]

    context = AssessContext(
        site_name=site.get("name", ""),
        city=site.get("city", ""),
        country=site.get("country", ""),
        catalogue=questions.catalogue_for_prompt(),
    )
    images = [ImageInput(role="upstream", data=prepared.data)]

    started = time.perf_counter()
    try:
        outcome = await suggest_with_fallback(settings, images, context)
    except Exception as exc:  # noqa: BLE001 - record it, keep going
        run.ok = False
        run.error = f"{type(exc).__name__}: {exc}"
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        return run

    run.latency_ms = outcome.latency_ms or int((time.perf_counter() - started) * 1000)
    run.degraded = outcome.degraded
    run.degraded_reason = outcome.degraded_reason
    run.provider = outcome.provider
    run.model = outcome.model
    run.is_mock = outcome.is_mock
    run.usage = vars(outcome.usage)

    chips, dropped = validate_suggestions(
        outcome.result.suggestions, questions, settings.low_confidence, prepared.ok
    )
    run.chips = [
        {
            "question_id": c.question_id,
            "codes": [c.suggested_code, *c.additional_codes],
            "confidence": c.confidence,
            "reason": c.reason,
            "needs_review": c.needs_review,
        }
        for c in chips
    ]
    run.dropped = [
        {"question_id": d.question_id, "codes": d.codes, "why": d.why} for d in dropped
    ]
    return run


def scorable(runs: list[PhotoRun]) -> list[PhotoRun]:
    """Runs that actually came from the configured model.

    A degraded run is MOCK output that stood in after the provider failed.
    Scoring it as the model's would silently mix a colour heuristic into the
    model's numbers - which is exactly the kind of quiet contamination this
    whole harness exists to catch.
    """
    return [r for r in runs if r.ok and not r.degraded]


def score(runs: list[PhotoRun], labels: dict) -> dict[str, QuestionStats]:
    stats: dict[str, QuestionStats] = defaultdict(lambda: QuestionStats(""))
    for run in runs:
        if not run.ok or run.degraded:
            continue
        for chip in run.chips:
            qid = chip["question_id"]
            if qid not in stats:
                stats[qid] = QuestionStats(qid)
            row = stats[qid]
            row.suggested += 1
            codes = set(chip["codes"])
            if UNKNOWN_CODE in codes:
                row.unknown += 1

            truth = labels.get((run.photo, qid))
            if truth:
                row.labelled += 1
                if codes == truth:
                    row.correct += 1
                    row.confidences_right.append(chip["confidence"])
                else:
                    row.confidences_wrong.append(chip["confidence"])

        for drop in run.dropped:
            qid = drop["question_id"]
            if qid not in stats:
                stats[qid] = QuestionStats(qid)
            stats[qid].dropped += 1
    return dict(stats)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def num(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def build_report(
    runs: list[PhotoRun],
    stats: dict[str, QuestionStats],
    labels: dict,
    questions,
    pricing: dict,
    settings,
    site: dict,
    prompt_version: str,
    usable: dict[str, bool] | None = None,
) -> str:
    good = scorable(runs)
    failed = [r for r in runs if not r.ok]
    degraded = [r for r in runs if r.ok and r.degraded]
    latencies = [r.latency_ms for r in good if r.latency_ms]

    total_chips = sum(s.suggested for s in stats.values())
    total_dropped = sum(s.dropped for s in stats.values())
    total_unknown = sum(s.unknown for s in stats.values())
    total_labelled = sum(s.labelled for s in stats.values())
    total_correct = sum(s.correct for s in stats.values())

    right = [c for s in stats.values() for c in s.confidences_right]
    wrong = [c for s in stats.values() for c in s.confidences_wrong]

    model = next((r.model for r in good if r.model), "unknown")
    is_mock = all(r.is_mock for r in good) if good else True
    prices = price_for(pricing, model)

    prompt_tokens = sum(r.usage.get("prompt_tokens", 0) for r in good)
    output_tokens = sum(
        r.usage.get("output_tokens", 0) + r.usage.get("thought_tokens", 0) for r in good
    )
    cost = (
        prompt_tokens * prices["input"] + output_tokens * prices["output"]
    ) / 1_000_000

    suggestable = len(questions.suggestable)
    coverage = (total_chips / (len(good) * suggestable)) if good and suggestable else None

    lines: list[str] = []
    add = lines.append

    add(f"# Evaluation — `{prompt_version}`")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        "by `eval/run_eval.py`.")
    add("")

    if is_mock:
        add("> **This run did NOT use a vision model.** Every figure below comes from")
        add("> the offline mock provider (a colour heuristic). Agreement and")
        add("> calibration numbers are meaningless here; drop rate, unknown rate and")
        add("> latency describe the harness and the validation gate, not a model.")
        add("")
    if degraded:
        add(f"> **{len(degraded)} photographs fell back to the mock provider and are")
        add(f"> EXCLUDED from every figure below.** They are mock output, not the")
        add(f"> model's, and scoring them would contaminate the result. Excluded: "
            f"{', '.join(sorted(r.photo for r in degraded))}. "
            f"Reason: {degraded[0].degraded_reason}")
        add("")
    if not labels:
        add("> **No labels filled in yet.** Agreement and calibration are blank.")
        add("> Fill in `eval/labels.csv` and re-run for those.")
        add("")

    # --- Setup ------------------------------------------------------------
    add("## Setup")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| Prompt | `{prompt_version}` |")
    add(f"| Provider | `{good[0].provider if good else 'n/a'}` |")
    add(f"| Model | `{model}` |")
    add(f"| Photos scored | {len(good)} of {len(runs)} "
        f"({len(failed)} unreadable, {len(degraded)} fell back to the mock) |")
    add(f"| Site context | {site.get('name', '?')}, {site.get('city', '?')} |")
    add(f"| Questions offered to the model | {suggestable} |")
    add(f"| Labelled answers | {total_labelled} |")
    add(f"| Timeout / retries | {settings.gemini_timeout_s:g}s / {settings.gemini_retries} |")
    add("")

    # --- Headline ---------------------------------------------------------
    add("## Headline")
    add("")
    add("| Measure | Value | What it means |")
    add("|---|---|---|")
    add(f"| Agreement with labels | {pct(total_correct / total_labelled if total_labelled else None)} "
        f"| {total_correct}/{total_labelled} suggestions matched the labeller exactly |")
    add(f"| Unknown (`NS`) rate | {pct(total_unknown / total_chips if total_chips else None)} "
        f"| {total_unknown}/{total_chips} suggestions were \"I'm not sure\" |")
    add(f"| Dropped by validation | {pct(total_dropped / (total_chips + total_dropped) if (total_chips + total_dropped) else None)} "
        f"| {total_dropped} invalid suggestions never reached a citizen |")
    add(f"| Coverage | {pct(coverage)} | share of offered questions the model answered |")
    add(f"| Mean confidence when right | {num(mean(right))} | |")
    add(f"| Mean confidence when wrong | {num(mean(wrong))} | a useful model is more confident when right |")
    gap = (mean(right) - mean(wrong)) if (right and wrong) else None
    add(f"| Calibration gap | {num(gap)} | right minus wrong; at or below zero the confidence is noise |")
    add("")

    # --- Latency and cost -------------------------------------------------
    add("## Latency and cost")
    add("")
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        add("| Measure | Value |")
        add("|---|---|")
        add(f"| Mean | {statistics.fmean(latencies):.0f} ms |")
        add(f"| Median | {statistics.median(latencies):.0f} ms |")
        add(f"| Slowest | {max(latencies)} ms |")
        add(f"| p95 | {p95} ms |")
    else:
        add("No successful calls to time.")
    add("")
    add(f"Tokens: {prompt_tokens:,} in, {output_tokens:,} out "
        "(thinking tokens counted as output).")
    add("")
    if prompt_tokens or output_tokens:
        per_photo = cost / len(good) if good else 0
        add(f"**Approximate cost: ${cost:.4f} for {len(good)} photos** "
            f"(${per_photo:.4f} each, so about ${per_photo * 1000:.2f} per 1,000).")
        add("")
        add(f"At ${prices['input']}/M input and ${prices['output']}/M output, from "
            f"`eval/pricing.json` (checked {pricing.get('checked', '?')}). "
            "Verify before quoting.")
    else:
        add("No token usage reported — cost cannot be estimated for this run.")
    add("")

    # --- Per question -----------------------------------------------------
    add("## Per question")
    add("")
    add("Sorted by drop rate, then by disagreement: the rows that need attention first.")
    add("")
    add("| Question | Asked | `NS` | Dropped | Labelled | Agreement | Conf. right | Conf. wrong |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")

    def sort_key(s: QuestionStats):
        total = s.suggested + s.dropped
        drop_rate = s.dropped / total if total else 0
        disagree = 1 - (s.agreement or 1)
        return (-drop_rate, -disagree, s.question_id)

    for s in sorted(stats.values(), key=sort_key):
        question = questions.get(s.question_id)
        label = question.raw["label"].get("en", s.question_id) if question else s.question_id
        add(
            f"| `{s.question_id}` — {label} | {s.suggested} | {s.unknown} | {s.dropped} "
            f"| {s.labelled} | {pct(s.agreement)} | {num(mean(s.confidences_right))} "
            f"| {num(mean(s.confidences_wrong))} |"
        )
    add("")

    # --- Never answered ---------------------------------------------------
    silent = [
        q.id for q in questions.suggestable
        if q.id not in stats or stats[q.id].suggested == 0
    ]
    if silent:
        add("### Questions the model never answered")
        add("")
        add("Either it is being appropriately cautious, or these questions cannot be")
        add("judged from a photograph and should be `ai_suggestable: false`.")
        add("")
        for qid in sorted(silent):
            question = questions.get(qid)
            label = question.raw["label"].get("en", qid) if question else qid
            add(f"- `{qid}` — {label}")
        add("")

    # --- Dropped detail ---------------------------------------------------
    drops = [(r.photo, d) for r in runs for d in r.dropped]
    if drops:
        add("### Every dropped suggestion")
        add("")
        add("| Photo | Question | Codes | Why |")
        add("|---|---|---|---|")
        for photo, drop in drops[:60]:
            add(f"| {photo} | `{drop['question_id']}` | "
                f"`{', '.join(drop['codes']) or '—'}` | {drop['why']} |")
        if len(drops) > 60:
            add(f"")
            add(f"...and {len(drops) - 60} more, in the JSON beside this report.")
        add("")

    # --- Failures ---------------------------------------------------------
    if failed:
        add("### Photos that could not be processed")
        add("")
        for run in failed:
            add(f"- `{run.photo}`: {run.error}")
        add("")

    # --- negative controls ------------------------------------------------
    usable = usable or {}
    controls = [r for r in good if usable.get(r.photo) is False]
    if controls:
        add("## Negative controls")
        add("")
        add(f"{len(controls)} of the {len(good)} images do not show a watercourse at "
            "all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells "
            "the model to stay silent on those. This counts whether it did.")
        add("")
        silent = [r for r in controls if not r.chips]
        add(f"- **Stayed silent on {len(silent)} of {len(controls)}** "
            f"({len(silent) / len(controls) * 100:.0f}%).")
        noisy = sorted((r for r in controls if r.chips),
                       key=lambda r: -len(r.chips))
        if noisy:
            add(f"- Offered suggestions anyway on {len(noisy)}:")
            add("")
            add("| Photo | Suggestions | Highest confidence |")
            add("|---|---:|---:|")
            for r in noisy[:12]:
                top = max((c["confidence"] for c in r.chips), default=0)
                add(f"| {r.photo} | {len(r.chips)} | {top:.2f} |")
        add("")

    add("## How to read this")
    add("")
    add("- **Dropped rate is the first thing to look at.** Anything above zero means")
    add("  the model is inventing codes the prompt did not offer it.")
    add("- **An unknown rate of zero is a red flag**, not a success: a model that is")
    add("  never unsure is guessing. On a mixed set, roughly a fifth to a third is")
    add("  healthy.")
    add("- **The calibration gap matters more than raw agreement.** A model that is")
    add("  70% accurate but visibly less confident when it is wrong is more useful in")
    add("  the field than one that is 80% accurate with flat confidence, because the")
    add("  citizen can tell which suggestions to check.")
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------

async def main_async(args) -> int:
    settings = get_settings()
    PROMPT_VER = prompt_version()
    questions = get_questions()
    sites = get_sites()

    site = sites.get(args.site) or (sites.all()[0] if sites.all() else {})

    photos_dir = Path(args.photos_dir) if args.photos_dir else PHOTOS_DIR
    photos = find_photos(args.limit, photos_dir)
    if not photos:
        print(f"No images found in {photos_dir}")
        print()
        print("Put your stream photographs there, then run:")
        print("    python eval/make_labels.py    # build the labels template")
        print("    python eval/run_eval.py       # measure the prompt")
        return 1

    labels = read_labels(Path(args.labels) if args.labels else None)
    pricing = load_pricing()

    print(f"Running {len(photos)} photo(s) through '{settings.ai_provider}'...")
    runs: list[PhotoRun] = []
    for index, path in enumerate(photos, start=1):
        run = await run_photo(path, site, settings, questions)
        runs.append(run)
        status = "ok" if run.ok else f"FAILED: {run.error}"
        flag = " [fell back to mock]" if run.degraded else ""
        print(
            f"  [{index}/{len(photos)}] {path.name}: {status} "
            f"({run.latency_ms} ms, {len(run.chips)} chips, "
            f"{len(run.dropped)} dropped){flag}"
        )

    stats = score(runs, labels)
    usable = read_usable(Path(args.labels) if args.labels else None)
    report = build_report(
        runs, stats, labels, questions, pricing, settings, site, PROMPT_VER, usable
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.label_suffix}" if args.label_suffix else ""
    report_path = REPORTS_DIR / f"{PROMPT_VER}{suffix}.md"
    report_path.write_text(report + "\n", encoding="utf-8")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = REPORTS_DIR / f"{PROMPT_VER}{suffix}-{stamp}.json"
    raw_path.write_text(
        json.dumps(
            {
                "prompt_version": PROMPT_VER,
                "generated_at": stamp,
                "provider": settings.ai_provider,
                "labels_filled": len(labels),
                "runs": [vars(r) for r in runs],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Report: {report_path}")
    print(f"Raw:    {raw_path}")
    return 0


def rebuild(json_path: Path, args) -> int:
    """Regenerate a report from a saved raw run - no API calls."""
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    runs = [PhotoRun(**row) for row in doc["runs"]]
    settings = get_settings()
    questions = get_questions()
    sites = get_sites()
    site = sites.get(args.site) or (sites.all()[0] if sites.all() else {})
    labels = read_labels(Path(args.labels) if args.labels else None)
    usable = read_usable(Path(args.labels) if args.labels else None)
    stats = score(runs, labels)
    version = doc.get("prompt_version", json_path.stem.split("-")[0])
    report = build_report(runs, stats, labels, questions, load_pricing(),
                          settings, site, version, usable)
    out = json_path.with_suffix("").with_name(
        json_path.name.split("-2")[0] + ".md")
    out.write_text(report + chr(10), encoding="utf-8")
    print(f"Rebuilt {out} from {json_path.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="only run the first N photos")
    parser.add_argument("--site", default="C1",
                        help="site id used for the prompt's context line")
    parser.add_argument("--label-suffix", default="",
                        help="suffix for the report filename, e.g. 'dry-run'")
    parser.add_argument("--photos-dir", default="",
                        help="read photos from here instead of eval/photos/")
    parser.add_argument("--rebuild", default="",
                        help="regenerate a report from a saved raw JSON run")
    parser.add_argument("--labels", default="",
                        help="read labels from here instead of eval/labels.csv")
    args = parser.parse_args()
    if args.rebuild:
        return rebuild(Path(args.rebuild), args)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
