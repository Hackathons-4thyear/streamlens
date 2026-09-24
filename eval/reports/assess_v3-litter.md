# Evaluation — `assess_v3`

Generated 2026-09-24 13:17 UTC by `eval/run_eval.py`.

> **10 photographs fell back to the mock provider and are
> EXCLUDED from every figure below.** They are mock output, not the
> model's, and scoring them would contaminate the result. Excluded: benevento_01.jpg, benevento_02.jpg, canal_01.jpg, culvert_01.jpg, drybed_01.jpg, erosion_01.jpg, gabion_01.jpg, gabion_02.jpg, giantreed_01.jpg, toulouse_02.jpg. Reason: The AI could not be reached.

## Setup

| | |
|---|---|
| Prompt | `assess_v3` |
| Provider | `gemini` |
| Model | `gemini-3.5-flash-lite` |
| Photos scored | 21 of 31 (0 unreadable, 10 fell back to the mock) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 18 |
| Labelled answers | 35 |
| Timeout / retries | 20s / 3 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement (exact match) | 83% | 29/35 suggestions matched the labeller exactly |
| Agreement (set overlap) | 87% | mean Jaccard; a correct superset earns partial credit |
| Unknown (`NS`) rate | 0% | 0/54 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 14% | share of offered questions the model answered |
| Mean confidence when right | 0.89 | |
| Mean confidence when wrong | 0.88 | a useful model is more confident when right |
| Calibration gap | 0.01 | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 30269 ms |
| Median | 18654 ms |
| Slowest | 83348 ms |
| p95 | 74620 ms |

Tokens: 106,990 in, 5,145 out (thinking tokens counted as output).

**Approximate cost: $0.0450 for 21 photos** ($0.0021 each, so about $2.14 per 1,000).

At $0.3/M input and $2.5/M output, from `eval/pricing.json` (checked 2026-09-24). Verify before quoting.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Exact | Overlap | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `construction` — Channel works | 3 | 0 | 0 | 3 | 67% | 67% | 0.90 | 0.90 |
| `bankType` — Bank type | 3 | 0 | 0 | 2 | 0% | 0% | — | 0.85 |
| `channelType` — Channel bed | 5 | 0 | 0 | 2 | 100% | 100% | 0.93 | — |
| `dams` — Longitudinal connectivity | 4 | 0 | 0 | 4 | 100% | 100% | 0.90 | — |
| `fallenBiomass` — Natural debris | 1 | 0 | 0 | 1 | 100% | 100% | 0.85 | — |
| `habitats` — Instream habitats | 3 | 0 | 0 | 3 | 0% | 50% | — | 0.88 |
| `imperviousL` — Impervious surface, left bank | 2 | 0 | 0 | 0 | — | — | — | — |
| `imperviousR` — Impervious surface, right bank | 2 | 0 | 0 | 0 | — | — | — | — |
| `litter` — Litter | 5 | 0 | 0 | 2 | 100% | 100% | 0.82 | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 5 | 0 | 0 | 3 | 100% | 100% | 0.90 | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 5 | 0 | 0 | 3 | 100% | 100% | 0.90 | — |
| `vegDominantL` — Dominant vegetation, left bank | 4 | 0 | 0 | 3 | 100% | 100% | 0.87 | — |
| `vegDominantR` — Dominant vegetation, right bank | 4 | 0 | 0 | 3 | 100% | 100% | 0.87 | — |
| `waterAspect` — Water aspect | 2 | 0 | 0 | 2 | 100% | 100% | 0.82 | — |
| `waterFlow` — Flow type | 6 | 0 | 0 | 4 | 100% | 100% | 0.93 | — |

### Questions the model never answered

Either it is being appropriately cautious, or these questions cannot be
judged from a photograph and should be `ai_suggestable: false`.

- `channelForm` — Channel form
- `pollutedPipes` — Polluted outfalls
- `sewage` — Sewage discharge

## Negative controls

11 of the 21 images do not show a watercourse at all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells the model to stay silent on those. This counts whether it did.

- **Stayed silent on 11 of 11** (100%).

## How to read this

- **Exact match against set overlap.** Where the two differ, the model is
  giving partly-right answers to choose-ALL questions - naming a real feature
  the labeller left out, or missing one. A large gap is a signal about the
  question, not only about the model.
- **Dropped rate is the first thing to look at.** Anything above zero means
  the model is inventing codes the prompt did not offer it.
- **An unknown rate of zero is a red flag**, not a success: a model that is
  never unsure is guessing. On a mixed set, roughly a fifth to a third is
  healthy.
- **The calibration gap matters more than raw agreement.** A model that is
  70% accurate but visibly less confident when it is wrong is more useful in
  the field than one that is 80% accurate with flat confidence, because the
  citizen can tell which suggestions to check.

