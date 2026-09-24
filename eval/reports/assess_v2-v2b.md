# Evaluation — `assess_v2`

Generated 2026-09-24 07:28 UTC by `eval/run_eval.py`.

## Setup

| | |
|---|---|
| Prompt | `assess_v2` |
| Provider | `gemini` |
| Model | `gemini-3.5-flash-lite` |
| Photos scored | 29 of 29 (0 unreadable, 0 fell back to the mock) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 17 |
| Labelled answers | 45 |
| Timeout / retries | 20s / 1 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement with labels | 91% | 41/45 suggestions matched the labeller exactly |
| Unknown (`NS`) rate | 2% | 2/82 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 17% | share of offered questions the model answered |
| Mean confidence when right | 0.89 | |
| Mean confidence when wrong | 0.82 | a useful model is more confident when right |
| Calibration gap | 0.07 | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 3998 ms |
| Median | 3025 ms |
| Slowest | 24716 ms |
| p95 | 6155 ms |

Tokens: 136,272 in, 6,919 out (thinking tokens counted as output).

**Approximate cost: $0.0582 for 29 photos** ($0.0020 each, so about $2.01 per 1,000).

At $0.3/M input and $2.5/M output, from `eval/pricing.json` (checked 2026-09-24). Verify before quoting.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Agreement | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bankType` — Bank type | 7 | 0 | 0 | 4 | 50% | 0.89 | 0.82 |
| `waterAspect` — Water aspect | 5 | 0 | 0 | 4 | 75% | 0.88 | 0.80 |
| `channelType` — Channel bed | 9 | 2 | 0 | 3 | 100% | 0.88 | — |
| `dams` — Longitudinal connectivity | 4 | 0 | 0 | 4 | 100% | 0.92 | — |
| `fallenBiomass` — Natural debris | 3 | 0 | 0 | 2 | 100% | 0.85 | — |
| `habitats` — Instream habitats | 4 | 0 | 0 | 1 | 0% | — | 0.85 |
| `imperviousL` — Impervious surface, left bank | 2 | 0 | 0 | 0 | — | — | — |
| `imperviousR` — Impervious surface, right bank | 2 | 0 | 0 | 0 | — | — | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 9 | 0 | 0 | 5 | 100% | 0.91 | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 8 | 0 | 0 | 5 | 100% | 0.91 | — |
| `vegDominantL` — Dominant vegetation, left bank | 8 | 0 | 0 | 5 | 100% | 0.88 | — |
| `vegDominantR` — Dominant vegetation, right bank | 8 | 0 | 0 | 5 | 100% | 0.87 | — |
| `waterFlow` — Flow type | 13 | 0 | 0 | 7 | 100% | 0.89 | — |

### Questions the model never answered

Either it is being appropriately cautious, or these questions cannot be
judged from a photograph and should be `ai_suggestable: false`.

- `channelForm` — Channel form
- `construction` — Channel works
- `pollutedPipes` — Polluted outfalls
- `sewage` — Sewage discharge

## Negative controls

13 of the 29 images do not show a watercourse at all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells the model to stay silent on those. This counts whether it did.

- **Stayed silent on 11 of 13** (85%).
- Offered suggestions anyway on 2:

| Photo | Suggestions | Highest confidence |
|---|---:|---:|
| gabion_01.jpg | 3 | 0.95 |
| gabion_02.jpg | 1 | 0.95 |

## How to read this

- **Dropped rate is the first thing to look at.** Anything above zero means
  the model is inventing codes the prompt did not offer it.
- **An unknown rate of zero is a red flag**, not a success: a model that is
  never unsure is guessing. On a mixed set, roughly a fifth to a third is
  healthy.
- **The calibration gap matters more than raw agreement.** A model that is
  70% accurate but visibly less confident when it is wrong is more useful in
  the field than one that is 80% accurate with flat confidence, because the
  citizen can tell which suggestions to check.

