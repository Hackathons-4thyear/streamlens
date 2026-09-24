# Evaluation — `assess_v3`

Generated 2026-09-24 08:21 UTC by `eval/run_eval.py`.

## Setup

| | |
|---|---|
| Prompt | `assess_v3` |
| Provider | `gemini` |
| Model | `gemini-3.5-flash-lite` |
| Photos scored | 29 of 29 (0 unreadable, 0 fell back to the mock) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 17 |
| Labelled answers | 58 |
| Timeout / retries | 20s / 3 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement (exact match) | 90% | 52/58 suggestions matched the labeller exactly |
| Agreement (set overlap) | 92% | mean Jaccard; a correct superset earns partial credit |
| Unknown (`NS`) rate | 1% | 1/96 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 19% | share of offered questions the model answered |
| Mean confidence when right | 0.87 | |
| Mean confidence when wrong | 0.83 | a useful model is more confident when right |
| Calibration gap | 0.04 | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 3981 ms |
| Median | 3842 ms |
| Slowest | 6586 ms |
| p95 | 6048 ms |

Tokens: 142,971 in, 8,689 out (thinking tokens counted as output).

**Approximate cost: $0.0646 for 29 photos** ($0.0022 each, so about $2.23 per 1,000).

At $0.3/M input and $2.5/M output, from `eval/pricing.json` (checked 2026-09-24). Verify before quoting.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Exact | Overlap | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `habitats` — Instream habitats | 6 | 0 | 0 | 4 | 25% | 62% | 0.80 | 0.85 |
| `construction` — Channel works | 2 | 0 | 0 | 2 | 50% | 50% | 0.85 | 0.90 |
| `waterAspect` — Water aspect | 8 | 0 | 0 | 5 | 80% | 80% | 0.86 | 0.70 |
| `bankType` — Bank type | 8 | 0 | 0 | 6 | 83% | 83% | 0.89 | 0.85 |
| `channelType` — Channel bed | 8 | 1 | 0 | 4 | 100% | 100% | 0.88 | — |
| `dams` — Longitudinal connectivity | 6 | 0 | 0 | 6 | 100% | 100% | 0.88 | — |
| `fallenBiomass` — Natural debris | 2 | 0 | 0 | 1 | 100% | 100% | 0.90 | — |
| `imperviousL` — Impervious surface, left bank | 5 | 0 | 0 | 1 | 100% | 100% | 0.85 | — |
| `imperviousR` — Impervious surface, right bank | 4 | 0 | 0 | 1 | 100% | 100% | 0.85 | — |
| `pollutedPipes` — Polluted outfalls | 1 | 0 | 0 | 1 | 100% | 100% | 0.75 | — |
| `sewage` — Sewage discharge | 1 | 0 | 0 | 1 | 100% | 100% | 0.80 | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 8 | 0 | 0 | 4 | 100% | 100% | 0.85 | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 7 | 0 | 0 | 4 | 100% | 100% | 0.88 | — |
| `vegDominantL` — Dominant vegetation, left bank | 9 | 0 | 0 | 6 | 100% | 100% | 0.87 | — |
| `vegDominantR` — Dominant vegetation, right bank | 9 | 0 | 0 | 6 | 100% | 100% | 0.87 | — |
| `waterFlow` — Flow type | 12 | 0 | 0 | 6 | 100% | 100% | 0.90 | — |

### Questions the model never answered

Either it is being appropriately cautious, or these questions cannot be
judged from a photograph and should be `ai_suggestable: false`.

- `channelForm` — Channel form

## Negative controls

13 of the 29 images do not show a watercourse at all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells the model to stay silent on those. This counts whether it did.

- **Stayed silent on 13 of 13** (100%).

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

