# Proposed changes for `assess_v2`

Status: **proposal only — nothing here has been applied.** `assess_v1` is still
the live prompt and `data/questions.json` is unchanged.

## What this is based on, and what it is not

It is honest to say up front that this proposal rests on **structural analysis,
not on measured model failures**. At the time of writing there is no API key, so
no vision model has ever seen a photograph through this system. The evidence
available is:

- the question set itself, and which questions a single still photograph can
  physically answer;
- the dry run in `reports/assess_v1-dry-run.md`, which exercised the full
  pipeline against the mock provider;
- the live failure-path test against the real Gemini endpoint (an invalid key
  produced a correctly classified `auth` failure, no retry, and a clean
  fallback).

Every item below is therefore a **hypothesis with a test attached**, not a
finding. The final comparison waits on labels.

---

## 1. Mark questions that a photograph cannot answer as `ai_suggestable: false`

This is the change most likely to matter, and the one you named.

Eight of the twenty-two AI-suggestable questions ask for something a single
still image cannot establish. Asking a model anyway invites a guess, and a
guess with a confidence number attached is worse than silence, because the
citizen has to work to undo it.

| Question | Why a photo cannot settle it |
|---|---|
| `waterFlow` | Speed is motion. A still frame cannot distinguish slow from standing, and standing from slow is exactly the distinction that matters ecologically. |
| `invasiveL` / `invasiveR` | Species identification from an uncontrolled wide shot. Getting this wrong in either direction is costly: a false positive triggers a pointless management response. |
| `cutsL` / `cutsR` | "Recent" is a time judgement. A photo shows cut stems, not when they were cut. |
| `withdrawal` | Absence of evidence. A pump twenty metres out of frame is invisible, so a confident "No" is unearned. |
| `dams` | Asks about the whole reach. One frame shows a few metres of it. |
| `vegDominantL` / `vegDominantR` | Plausible from a good photo, but needs the bank in frame and unshaded. Worth keeping as suggestable and watching its numbers rather than removing it. |

**Proposed:** set `ai_suggestable: false` for `waterFlow`, `invasiveL`,
`invasiveR`, `cutsL`, `cutsR` and `withdrawal`. Keep `dams` and the
`vegDominant*` pair, but watch them.

The citizen still answers all of these — they simply appear without a chip,
which the Review screen already handles. This is not a reduction in what
StreamLens asks; it is a reduction in what it pretends a model can see.

**How to test it:** these six are exactly the questions where `assess_v1` should
show a high `NS` rate or poor agreement. If the measured run instead shows the
model answering them accurately, the hypothesis is wrong and they should stay.
Do not apply this change before looking.

## 2. Move the answer codes closer to the point of use

`assess_v1` puts every rule before the question catalogue, so by the time the
model reaches `impervious L/R` it is a long way from "use only the exact codes
listed". The drop rate will show whether this matters.

**Proposed:** repeat the code list as a compact closing constraint after the
catalogue, and state once more that anything outside it is discarded.

**How to test it:** dropped rate. If `assess_v1` already drops nothing, this
change is unnecessary and should not be made — extra prompt text is not free,
and a longer prompt costs input tokens on every call.

## 3. Make the confidence scale concrete

`assess_v1` describes confidence bands in words ("unmistakable", "clearly
visible"). Models tend to cluster on such scales, which would show up as a
calibration gap near zero — the failure the dry run already exhibits for the
mock heuristic (−0.02, because its confidence is noise by construction).

**Proposed:** anchor each band to an observable test, e.g. *0.9+: you could point
at the pixels that prove it; 0.5–0.7: you are inferring from partial evidence;
below 0.5: do not send it.*

**How to test it:** the calibration gap. If it is already comfortably positive,
leave the wording alone.

## 4. Ask for the evidence before the answer

Currently the model gives a code and then a reason, so the reason is written
after the decision and can rationalise it. Asking for a one-clause observation
*first*, then the code, tends to make the answer follow the evidence.

**Proposed:** add an `observation` field to the response schema, ordered before
`codes`, and drop it before the chip reaches the UI — it is a thinking aid, not
something the citizen needs.

**Cost note:** this adds output tokens on every suggestion. Measure whether the
agreement improvement justifies it; if not, drop it.

## 5. Consider `gemini-2.5-flash-lite` for the field

Per `pricing.json`, Flash-Lite is roughly a third the input price and a sixth
the output price of Flash. For a task that is mostly "name what is in this
picture from a fixed list", it may well be sufficient.

**How to test it:** run the same photographs and labels through both and compare
agreement, drop rate and calibration against the cost difference. The harness
takes the model from settings, so this is two runs and no code change.

---

## Order of work, once labels exist

1. Run `assess_v1` against the real model and the real labels. **Do not change
   the prompt first** — without a baseline, nothing after it is measurable.
2. Apply only the changes the baseline actually justifies. A change that cannot
   point at a number it is meant to move should not be made.
3. Re-run, and commit both reports side by side.
4. Keep `assess_v1.md` in the repository. A prompt version that has been measured
   is worth more than a tidy folder.
