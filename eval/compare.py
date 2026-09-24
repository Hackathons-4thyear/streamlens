"""Compare two evaluation runs and write a side-by-side markdown table.

Reads the raw JSON that `run_eval.py` writes beside each report, re-scores both
against the same labels, and reports where they differ. Re-scoring rather than
parsing the markdown means the two runs are always measured the same way.

Usage:
    python eval/compare.py --a reports/assess_v1-<stamp>.json \
                           --b reports/assess_v2-<stamp>.json \
                           --out reports/v1-vs-v2.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.questions import get_questions  # noqa: E402
from run_eval import PhotoRun, read_labels, score  # noqa: E402

UNKNOWN_CODE = "NS"


def load_runs(path: Path) -> tuple[list[PhotoRun], dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    runs = [PhotoRun(**row) for row in doc["runs"]]
    return runs, doc


def totals(runs: list[PhotoRun], labels: dict, suggestable: int) -> dict:
    stats = score(runs, labels)
    good = [r for r in runs if r.ok]
    chips = sum(s.suggested for s in stats.values())
    dropped = sum(s.dropped for s in stats.values())
    unknown = sum(s.unknown for s in stats.values())
    labelled = sum(s.labelled for s in stats.values())
    correct = sum(s.correct for s in stats.values())
    right = [c for s in stats.values() for c in s.confidences_right]
    wrong = [c for s in stats.values() for c in s.confidences_wrong]
    latencies = [r.latency_ms for r in good if r.latency_ms]

    prompt_tokens = sum(r.usage.get("prompt_tokens", 0) for r in good)
    output_tokens = sum(
        r.usage.get("output_tokens", 0) + r.usage.get("thought_tokens", 0) for r in good
    )

    return {
        "photos": len(good),
        "chips": chips,
        "dropped": dropped,
        "unknown": unknown,
        "labelled": labelled,
        "correct": correct,
        "agreement": correct / labelled if labelled else None,
        "unknown_rate": unknown / chips if chips else None,
        "drop_rate": dropped / (chips + dropped) if (chips + dropped) else None,
        "coverage": chips / (len(good) * suggestable) if good and suggestable else None,
        "conf_right": statistics.fmean(right) if right else None,
        "conf_wrong": statistics.fmean(wrong) if wrong else None,
        "gap": (statistics.fmean(right) - statistics.fmean(wrong))
        if (right and wrong) else None,
        "latency_mean": statistics.fmean(latencies) if latencies else None,
        "latency_median": statistics.median(latencies) if latencies else None,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "stats": stats,
    }


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def num(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def delta(a: float | None, b: float | None, higher_is_better: bool, as_pct=True) -> str:
    if a is None or b is None:
        return "—"
    diff = b - a
    if abs(diff) < 1e-9:
        return "no change"
    shown = f"{diff * 100:+.0f} pts" if as_pct else f"{diff:+.2f}"
    better = (diff > 0) == higher_is_better
    return f"{shown} {'✅' if better else '❌'}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True, help="raw JSON of the baseline run")
    parser.add_argument("--b", required=True, help="raw JSON of the new run")
    parser.add_argument("--name-a", default="assess_v1")
    parser.add_argument("--name-b", default="assess_v2")
    parser.add_argument("--labels", default=str(EVAL_DIR / "labels.csv"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--suggestable-a", type=int, default=0,
                        help="how many questions run A was offered (default: current catalogue)")
    parser.add_argument("--suggestable-b", type=int, default=0)
    args = parser.parse_args()

    labels = read_labels(Path(args.labels))
    questions = get_questions()
    suggestable = len(questions.suggestable)

    runs_a, doc_a = load_runs(Path(args.a))
    runs_b, doc_b = load_runs(Path(args.b))
    a = totals(runs_a, labels, args.suggestable_a or suggestable)
    b = totals(runs_b, labels, args.suggestable_b or suggestable)

    lines: list[str] = []
    add = lines.append
    add(f"# `{args.name_a}` vs `{args.name_b}`")
    add("")
    add(f"Same {a['photos']} photographs, same {len(labels)} labels, re-scored "
        "identically for both runs.")
    add("")
    add(f"`{args.name_a}` was offered {args.suggestable_a or suggestable} questions; "
        f"`{args.name_b}` was offered {args.suggestable_b or suggestable}. Coverage is "
        "a share of each run's own catalogue, so the two coverage figures are not "
        "directly comparable - the suggestion count is.")
    add("")
    add(f"| Measure | `{args.name_a}` | `{args.name_b}` | Change |")
    add("|---|---:|---:|---|")
    add(f"| Agreement with labeller | {pct(a['agreement'])} | {pct(b['agreement'])} "
        f"| {delta(a['agreement'], b['agreement'], True)} |")
    add(f"| Dropped by validation | {pct(a['drop_rate'])} | {pct(b['drop_rate'])} "
        f"| {delta(a['drop_rate'], b['drop_rate'], False)} |")
    add(f"| Unknown (`NS`) rate | {pct(a['unknown_rate'])} | {pct(b['unknown_rate'])} "
        f"| {delta(a['unknown_rate'], b['unknown_rate'], True)} |")
    add(f"| Coverage of offered questions | {pct(a['coverage'])} | {pct(b['coverage'])} "
        f"| {delta(a['coverage'], b['coverage'], True)} |")
    add(f"| Confidence when agreeing | {num(a['conf_right'])} | {num(b['conf_right'])} "
        f"| {delta(a['conf_right'], b['conf_right'], True, as_pct=False)} |")
    add(f"| Confidence when disagreeing | {num(a['conf_wrong'])} | {num(b['conf_wrong'])} "
        f"| {delta(a['conf_wrong'], b['conf_wrong'], False, as_pct=False)} |")
    add(f"| Calibration gap | {num(a['gap'])} | {num(b['gap'])} "
        f"| {delta(a['gap'], b['gap'], True, as_pct=False)} |")
    add(f"| Suggestions offered | {a['chips']} | {b['chips']} | {b['chips'] - a['chips']:+d} |")
    add(f"| Labelled comparisons | {a['labelled']} | {b['labelled']} "
        f"| {b['labelled'] - a['labelled']:+d} |")
    add(f"| Mean latency | {num(a['latency_mean'], 0)} ms | {num(b['latency_mean'], 0)} ms "
        f"| {delta(a['latency_mean'], b['latency_mean'], False, as_pct=False)} |")
    add(f"| Input tokens | {a['prompt_tokens']:,} | {b['prompt_tokens']:,} "
        f"| {b['prompt_tokens'] - a['prompt_tokens']:+,} |")
    add(f"| Output tokens | {a['output_tokens']:,} | {b['output_tokens']:,} "
        f"| {b['output_tokens'] - a['output_tokens']:+,} |")
    add("")

    add("## Per question")
    add("")
    add(f"| Question | {args.name_a} agree | {args.name_b} agree "
        f"| {args.name_a} `NS` | {args.name_b} `NS` |")
    add("|---|---:|---:|---:|---:|")
    for qid in sorted(set(a["stats"]) | set(b["stats"])):
        sa = a["stats"].get(qid)
        sb = b["stats"].get(qid)
        add(f"| `{qid}` | {pct(sa.agreement) if sa else '—'} "
            f"| {pct(sb.agreement) if sb else '—'} "
            f"| {sa.unknown if sa else '—'} | {sb.unknown if sb else '—'} |")
    add("")

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
