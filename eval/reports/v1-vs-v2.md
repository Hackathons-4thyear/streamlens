# `assess_v1` vs `assess_v2`

Same 29 photographs, same 129 labels, re-scored identically for both runs.

`assess_v1` was offered 22 questions; `assess_v2` was offered 17. Coverage is a share of each run's own catalogue, so the two coverage figures are not directly comparable - the suggestion count is.

| Measure | `assess_v1` | `assess_v2` | Change |
|---|---:|---:|---|
| Agreement with labeller | 89% | 91% | +2 pts ✅ |
| Dropped by validation | 0% | 0% | no change |
| Unknown (`NS`) rate | 0% | 2% | +2 pts ✅ |
| Coverage of offered questions | 14% | 17% | +2 pts ✅ |
| Confidence when agreeing | 0.87 | 0.89 | +0.03 ✅ |
| Confidence when disagreeing | 0.84 | 0.82 | -0.02 ✅ |
| Calibration gap | 0.03 | 0.07 | +0.04 ✅ |
| Suggestions offered | 91 | 82 | -9 |
| Labelled comparisons | 57 | 45 | -12 |
| Mean latency | 3838 ms | 3998 ms | +159.93 ❌ |
| Input tokens | 139,839 | 136,272 | -3,567 |
| Output tokens | 6,274 | 6,919 | +645 |

## Per question

| Question | assess_v1 agree | assess_v2 agree | assess_v1 `NS` | assess_v2 `NS` |
|---|---:|---:|---:|---:|
| `bankType` | 50% | 50% | 0 | 0 |
| `channelForm` | — | — | 0 | — |
| `channelType` | 100% | 100% | 0 | 2 |
| `construction` | 67% | — | 0 | — |
| `cutsL` | — | — | 0 | — |
| `cutsR` | — | — | 0 | — |
| `dams` | 100% | 100% | 0 | 0 |
| `fallenBiomass` | 100% | 100% | 0 | 0 |
| `habitats` | 50% | 0% | 0 | 0 |
| `imperviousL` | 100% | — | 0 | 0 |
| `imperviousR` | 100% | — | 0 | 0 |
| `invasiveL` | — | — | 0 | — |
| `invasiveR` | — | — | 0 | — |
| `pollutedPipes` | 100% | — | 0 | — |
| `sewage` | 100% | — | 0 | — |
| `vegCoverL` | 100% | 100% | 0 | 0 |
| `vegCoverR` | 100% | 100% | 0 | 0 |
| `vegDominantL` | 100% | 100% | 0 | 0 |
| `vegDominantR` | 100% | 100% | 0 | 0 |
| `waterAspect` | 50% | 75% | 0 | 0 |
| `waterFlow` | 100% | 100% | 0 | 0 |
| `withdrawal` | — | — | 0 | — |


## Verdict: keep `assess_v2`

It agrees with the labeller more often, separates confident-right from
confident-wrong better, drops nothing, and offers a `not sure` answer at all -
`assess_v1` never once said it was unsure. Both changes that `assess_v2` bundles
(the prompt rewrite and the catalogue change) are shipped together, so the
comparison attributes the difference to the pair, not to either alone.

**`assess_v2` is now the default** (`ASSESS_PROMPT=assess_v2`).

## What actually happened, in order

Three runs, not two. Reporting all three because the middle one is where the
useful findings are.

| Run | Prompt | Questions offered | Photos scored | Agreement | Drops | Calibration gap |
|---|---|---:|---:|---:|---:|---:|
| 1 | `assess_v1` | 22 | 29 | 89% | 0% | 0.03 |
| 2 | `assess_v2` | 16 (all six retired) | 27 | 89% | 0% | 0.06 |
| 3 | `assess_v2` | 17 (`waterFlow` kept) | 29 | **91%** | 0% | **0.07** |

### The proposal was wrong about `waterFlow`, and the baseline said so

`eval/assess_v2-proposal.md` argued that six questions should stop being
suggested because a still photograph cannot answer them, and `waterFlow` was
top of that list: *"Speed is motion. A still frame cannot distinguish slow from
standing."*

The baseline refuted it. `assess_v1` answered `waterFlow` on **14 of 29**
photographs - the most-used question in the whole set - and agreed with the
labeller on **7 of 7** checked, at 0.89 mean confidence. The reasoning in the
proposal was about a distinction (slow vs standing) that turned out not to be
the distinction that matters in practice: the answers actually given were `DRY`
and `FAS`, and a dry bed and white broken water are both plainly visible in a
still frame.

Retiring it (run 2) removed the single best-performing question for no gain.
Run 3 put it back. The other five stay retired - but honestly, the data is
*silent* on them rather than supporting them: the model volunteered
`invasiveL/R`, `cutsL/R` and `withdrawal` only 1-2 times each across 29 photos,
and the labeller could not answer them either, so there is nothing to compare.
They are retired on the argument in the proposal, not on evidence.

### A harness bug that would have published a wrong number

Run 2 first reported a **10% drop rate**, which would have read as the new
prompt making the model invent codes. It was not. Two photographs had exhausted
their retries and fallen back to the `MockProvider`, and the harness was scoring
that mock output as if it were the model's. Every one of the twelve "drops" was
the mock answering the six retired questions with `NS`.

`eval/run_eval.py` now excludes fallback runs from every figure and names them
at the top of the report. Reports say `Photos scored: 27 of 29` rather than
quietly averaging a colour heuristic into a model's score.

## Where the two models disagreed

Four cases, and in two of them the model has the better claim.

**`weir_01.jpg` — `construction`: Gemini `Y` (0.95), labeller `N`.**
Gemini: *"Fresh concrete structures and bare disturbed earth are clearly visible
next to the channel."* Looking again, it is right and the label is wrong - the
concrete is unweathered and the surrounding ground is bare rubble. The labeller
was being conservative about "active works" when the question asks about works
generally. **Scored as a disagreement; should be read as a labelling error.**

**`outfall_02.jpg` and `pollution_01.jpg` — `bankType`: Gemini `NAT`, labeller `ART`.**
Gemini answered about the wider bank (mud, earth, soil-retention matting); the
labeller answered about the engineered structure in the middle of the frame
(sheet piling, concrete walls). Both readings are defensible, which means **the
question is ambiguous**, not that either party is wrong. `bankType` does not say
whether to describe the bank as a whole or the hardest thing on it. That is a
question-design finding worth taking back to the catalogue.

**`streambed_01.jpg` — `habitats`: Gemini `SD,RF`, labeller `SD`.**
Gemini also spotted riffles further upstream, which are genuinely there. The
scorer requires an exact set match, so a correct superset counts as a full
disagreement. **This is a scoring artefact**: for choose-ALL questions, partial
credit would describe reality better than exact match does.

**`benevento_01.jpg` — `waterAspect`: Gemini `CO` (unusual colour), labeller `MU` (muddy).**
The water is a strong opaque green. "Muddy or cloudy" and "an unusual colour"
both fit it, and the answer list does not separate them. Genuine ambiguity, no
error on either side.

Of six scored disagreements in the baseline, on this reading **one is a labeller
error, two are ambiguous questions, and one is a scoring artefact**. The honest
conclusion is that 89-91% understates how often the two readings are compatible -
and equally, that a 45-comparison sample cannot support a confident claim either
way.

## What this does not show

- **No human expert was involved.** Both sides are AI. The "labeller" is Claude
  (the coding agent) viewing each photograph; the "model" is Gemini. Agreement
  between two AI systems is not accuracy, and where they agree they may be
  agreeing on the same mistake.
- **The sample is tiny.** 29 photographs, 129 labels, 45-57 scored comparisons.
  Per-question rows with two or three observations are anecdote. A 2-point
  difference in agreement is well inside the noise.
- **These are web photographs, not app submissions.** Wikimedia Commons images
  chosen by category, framed by photographers with other purposes - not phone
  snaps taken by a volunteer standing on a bank following the app's guidance.
  Thirteen of the 29 turned out not to show a watercourse at all.
- **One photograph per assessment**, where the real flow sends an upstream and a
  downstream view.
- **One model, on one afternoon.** `gemini-3.6-flash` was unusable throughout
  (503 under sustained load), so these numbers are `gemini-3.5-flash-lite`.
