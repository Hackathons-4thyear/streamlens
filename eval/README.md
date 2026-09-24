# Evaluation harness

Measures the assessment prompt against real photographs, so changes to it are
judged by numbers rather than by how the output reads.

## Running it

```bash
# 1. put photographs in eval/photos/   (see that folder's README)
# 2. build the labels template
python eval/make_labels.py

# 3. fill in the 'code' column of eval/labels.csv - your own answers
# 4. measure
python eval/run_eval.py
```

The report lands in `eval/reports/<prompt_version>.md`, with the raw run beside
it as timestamped JSON. **Both are committed.** A prompt change that cannot show
its effect on these numbers is a guess.

Useful flags:

| Flag | Purpose |
|---|---|
| `--limit 5` | run only the first five photos, for a cheap smoke test |
| `--site C1` | the site whose name and city go into the prompt's context line |
| `--photos-dir DIR` | read photos from somewhere other than `eval/photos/` |
| `--labels FILE` | read labels from somewhere other than `eval/labels.csv` |
| `--label-suffix NAME` | suffix the report filename, e.g. `assess_v1-dry-run.md` |

## Labels

`eval/labels.csv` has one row per photo per AI-suggestable question, pre-filled
with the question text and its allowed codes. You fill in `code` only.

- **Choose-ONE questions** take one code: `NAT`
- **Choose-ALL questions** take several, separated by a semicolon: `SB;RF`
- **Leave a row blank** if you cannot tell from the photo either. A blank row is
  skipped entirely and is not counted against the model. This matters: a
  question you cannot answer from a photograph is not one the model should be
  penalised for, it is a question that should probably not be asked of a model
  at all.

Re-running `make_labels.py` preserves codes you have already filled in, so new
photographs can be added without losing work.

## What the numbers mean

**Read them in this order.**

1. **Dropped rate.** Suggestions thrown out by validation because they named a
   question that does not exist, or a code that is not an option of it. Anything
   above zero means the model is inventing answers and the prompt's code list is
   not landing. This is the sharpest signal a prompt is failing, and it needs no
   labels at all.
2. **Unknown (`NS`) rate.** How often the model said "I'm not sure". **Zero is a
   red flag, not a success** — a model that is never unsure is guessing. On a
   mixed set, roughly a fifth to a third is healthy. Look also at the list of
   questions the model never answered: either it is being appropriately
   cautious, or those questions cannot be judged from a photograph and should be
   marked `ai_suggestable: false` in `data/questions.json`.
3. **Calibration gap** — mean confidence when right minus mean confidence when
   wrong. This matters more than raw agreement. A model that is 70% accurate but
   visibly less sure when it is wrong is more useful in the field than one that
   is 80% accurate with flat confidence, because the citizen can tell which
   suggestions deserve a second look. A gap at or below zero means the
   confidence number is noise and should not be shown as a bar.
4. **Agreement.** Exact match on the code set. Useful, but the least interesting
   of the four: a prompt can score well here and still be dangerous if it is
   confidently wrong on the questions that matter.

## Honesty about the method

- **One labeller.** These are one person's answers, not a consensus of
  ecologists. Where the label and the model disagree, the label is not
  automatically right.
- **Small sample.** Tens of photographs, not thousands. Treat per-question rows
  with a handful of observations as anecdote.
- **Single photo per assessment.** The live app sends an upstream and a
  downstream view; the harness sends one image as `upstream`. Questions that
  need both views are therefore harder here than in the app.
- **Costs are approximate.** They depend on `eval/pricing.json` being current.
  Check the source before quoting a figure anywhere that matters.
- **The harness uses the real code path.** Photo preparation and answer
  validation are imported from `api/app`, not reimplemented, so the drop rate it
  reports is the drop rate citizens would have seen.

## Without an API key

With no `GEMINI_API_KEY`, the harness runs against the mock provider and the
report says so in a banner at the top. Agreement and calibration are meaningless
in that mode; drop rate, unknown rate and latency describe the harness and the
validation gate rather than a model. It is still worth running — it proves the
pipeline works before you spend anything.
