# StreamLens — status

Written for: the judges and anyone picking this repository up mid-build.

Last updated: 24 September 2026.

Phase 1 delivered the **Observe** vertical slice. Phase 1.5 measured the vision
prompt against real photographs. Phase 2 built **Understand & Act**. Phase 3 is
designed but not built. This document says exactly which is which, because a demo
that hides its seams wastes a reviewer's time.

---

## What works

### The loop, end to end
Pick a site → take upstream and downstream photos → get AI suggestion chips →
confirm, change or reject each one → give your own overall rating and emotions →
consent → send. Verified against the running stack, not only in tests: a
submission stored with two photos, three answers and a measured AI agreement
rate of 0.5 (one suggestion kept, one overridden).

### AI suggests, humans decide — enforced in three places
- **The prompt** (`api/app/ai/prompts/assess_v3.md`, loaded from disk at call
  time) tells the model the `overall` question does not exist for it.
- **The API** drops any suggestion for a question marked `ai_suggestable: false`,
  even at confidence 1.0. There is a test that tries exactly that and asserts it
  is refused.
- **The web app** starts every chip as `pending`, holding no answer. A chip the
  citizen never touched is not submitted. Silence is not consent.

Each stored answer keeps the citizen's choice *and* the AI's suggestion, so
disagreement is measurable rather than invisible.

### Answer validation
Every code a provider returns is checked against `data/questions.json` before a
citizen can see it. Unknown questions, invented codes, duplicates, and multiple
codes on a single-answer question are all discarded into a `dropped` list that
the UI surfaces. A failing prompt shows up as visible drops, not silent nonsense.

### The mock provider, honestly labelled
With no `GEMINI_API_KEY`, StreamLens runs a deterministic colour heuristic. The
API returns `is_mock: true`, and the UI shows a **"demo AI (mock)"** badge plus a
full explanatory notice. The demo works with no key, no network and no cost, and
never pretends to be a vision model.

### Photo handling
EXIF orientation is applied, then *all* metadata — including any GPS the camera
embedded — is destroyed by rebuilding the image from raw pixels. Images are
downscaled to 1600 px. Blur is measured as the variance of the Laplacian and
brightness as mean luma; blurry, dark and overexposed photos produce warnings,
and bad photo quality flags every suggestion for extra review.

### Offline
The site list and question set are cached in IndexedDB, so a cold start with no
signal works. Submissions queue with their photos and flush on reconnect. A
network failure keeps an item queued; a 4xx marks it permanently failed instead
of retrying a bad payload forever. Photos are stored as `ArrayBuffer`, not
`Blob`, because Safari has shipped IndexedDB versions that lose Blobs.

### Data provenance
- **106 real research sites** fetched once from the public ENORA endpoint into
  `data/sites.json` and served locally. Attributed in the file, the API response
  and the UI.
- **23 questions** in `data/questions.json`. The app's own question endpoint
  requires authentication, so ids and answer codes come from a public draft FHIR
  CodeSystem, marked `source: "streamcheck-fhir-docs"` per question and option.
  Our explanations, glossary and translations are marked `source: "manual"`.
  Nothing is presented as an official OneAquaHealth artefact.
- Non-English strings are flagged `machine_translated`, and the UI says so.

### Accessibility
44 px minimum tap targets, visible focus rings, WCAG AA contrast pairings
documented in `web/src/index.css`, labelled controls, and a glossary built as a
tappable popover rather than a hover tooltip — hover does not exist on a phone.

### Tests
- **168 pytest tests**, none touching the network.
- **22 vitest tests** covering the answer state machine and the offline outbox.
- TypeScript compiles clean under `strict`.

---

## What is stubbed or missing

| Area | State | Why |
|---|---|---|
| **Gemini provider** | Verified against the live API | Runs on `gemini-3.5-flash-lite`. `gemini-2.5-flash` is retired for new keys and `gemini-3.6-flash` returned 503 on every one of 29 sequential calls, so it is unusable under load. |
| **Question translations** | English and Portuguese complete; it, fr, nl, no fall back to English | Priority was the working vertical slice. Interface chrome *is* translated into all six. |
| **All translations** | Ours, not the consortium's | Flagged `machine_translated` in the data and warned about in the UI. A native speaker should review before field use. |
| **Photo storage** | Files on local disk | Fine for a demo; a real deployment needs object storage and a retention policy. |
| **Authentication** | None | Anyone who can reach the API can post an observation. Acceptable for a hackathon demo, not for production. |
| **`GET /observations`** | Unpaginated, capped at 200 | Demo convenience endpoint, not a real query API. |
| **PWA install** | Manifest and service worker build correctly | Not tested on a physical phone. |
| **"Answer contradicts the photo" check** | Not built | Blur, brightness, GPS distance and the watercourse gate exist. Cross-answer consistency does not. |
| **Phase 3** | Not started | Quests, leaderboard, wellbeing mirror, FHIR export. |

---

## Phase 2 — Understand & Act (built)

### The watercourse gate
`assess_v3` returns `is_watercourse` in the same structured response as the
suggestions, so it costs no extra call. When it is false the API returns no
chips at all and the review screen asks for a different photo. Measured on the
same 29 evaluation photographs, silence on the 13 images that show no
watercourse went from **10/13 to 13/13**.

### Stream health card
Built only from citizen-confirmed answers. Sections graded by how many of their
answered questions match a known problem in the measures catalogue — a rule a
reader can check. Carries **"indicator view, not a validated ecological index"**
in the payload and on screen. Includes rating history, visit count, last visit,
a data-completeness meter and averaged emotions.

### 48-hour alerts
Three rules in `data/alert_rules.json`, executed by `app/alerts.py`:

| Rule | Fires when |
|---|---|
| `sewage_overflow_risk` | ≥20 mm forecast rain **and** a sewage or polluted-pipe report within 14 days |
| `mosquito_breeding_conditions` | ≥20 °C forecast **and** standing or dry water reported within 21 days |
| `debris_blockage_watch` | ≥25 mm forecast rain **and** a barrier or fallen wood reported within 60 days |

Every threshold carries its own source. The 72-hour advice figure is quoted from
Directive 2006/7/EC Article 2; the mosquito temperature reasoning cites published
Culex development rates. **The rainfall triggers say `project judgement`** and
explain why: no pan-European figure defines when a combined sewer spills, and the
UK Met Office dropped fixed millimetre thresholds in 2011. Nothing borrows an
unrelated citation to look authoritative.

No rule fires on weather alone — weather is not a property of a stream, so each
also needs a citizen observation. Every alert shows the numbers that triggered
it, and a test asserts no alert ever uses a banned word or omits "Check official
local advice."

### Measures
`data/measures.json`: 25 measures across 10 observable problems, from the
OneAquaHealth D2.4 catalogue (DOI 10.5281/zenodo.20040211, CC-BY-4.0).
`scripts/build_measures.py` opens the PDF and confirms each cited page still
names the measure cited against it — **25 of 25 confirmed**. The mapping,
plain-language text, health co-benefit tags and effort estimates are ours and
marked `project judgement (StreamLens)`, because the catalogue links health at
p.132 in general terms rather than measure by measure.

### Weather
Open-Meteo, cached one hour per site, stale cache served offline **with its
timestamp and a stale flag**. With neither forecast nor cache, the engine
produces no weather-based alerts rather than failing the page.

### Demo data
`scripts/seed_demo.py` writes 101 observations across 12 sites in all five
cities over 90 days, every one `synthetic: true`. A scope toggle (all / real /
demo) sits on every view and is passed to the API. Two sites get **planted
forecasts** so the rain-driven rules can be shown on a dry day; these are flagged
`_streamlens_synthetic`, reported by the API and badged "demo forecast" on
screen. `--no-demo-weather` turns that off.

### Screens
Site page (alerts, health card, measures), Home "alerts near you", and a
sortable city table with CSV export for municipal users.

---

## What Phase 2 did NOT do

| Area | State |
|---|---|
| **Litter** | Inferred from `waterAspect: CO` rather than asked directly. It needs its own question; `measures.json` says so in `detection_note`. |
| **City page polish** | Functional sortable table with CSV, but no charts or map view. |
| **Alert delivery** | Alerts are shown when you open a site. No push, no email, no subscriptions. |
| **Thresholds** | Rainfall triggers are our judgement, not calibrated to any real catchment. A municipality must replace them. |
| **Health card weighting** | Every question counts equally within a section. A real index would weight them. |
| **Measures** | 25 of roughly 60 in the catalogue, chosen for the problems StreamLens can observe. |
| **Phase 3** | Not started: quests, leaderboard, wellbeing mirror, FHIR export. |

---

## Suggested next steps

### Phase 2 — Understand & Act

1. **Stream health card.** A read model over stored observations for one site:
   latest rating, trend, which pressures were reported and how often, when it was
   last visited. Needs an aggregation endpoint; the data is already shaped for it
   since answers are stored per question with codes.
2. **48-hour alert.** A rules engine, not a model, so every alert can show its
   reasons. Inputs: Open-Meteo rain and temperature forecast for the site
   coordinates, plus recent `sewage`, `pollutedPipes` and `waterFlow: STA`
   reports. Output: a level plus the list of rules that fired, each with the
   number that triggered it. Rules belong in a JSON file, not in Python, so a
   scientist can read and change them.
   **Keep the no-medical-claims rule here.** An alert says "sewage was reported
   twice this week and 30 mm of rain is forecast", never "this water is unsafe".
3. **Restoration measures table.** Map observed problems to measures from the
   OneAquaHealth catalogue, in `data/measures.json` with the same per-entry
   provenance discipline as `questions.json`. Each row: the problem, the measure,
   the expected ecological effect, and the claimed health benefit *with its
   source*. Where the catalogue is not publicly available, mark entries `manual`
   and say so.

### Phase 3 — Return

4. **Quests from real data gaps.** Compute them: sites with no visit in N days,
   sites never seen after rain (join the visit dates against Open-Meteo history),
   seasons missing for a site. A quest that points at a genuine gap is worth ten
   that gamify busywork.
5. **Points and leaderboard.** Award for photo quality (the blur and brightness
   scores already exist) and for agreement with other visitors to the same site
   within a window. Resist rewarding volume alone — it pays people to submit
   rubbish. Team-level board only; an individual board on a scientific dataset
   creates an incentive to fabricate.
6. **Wellbeing mirror.** Aggregate the emotion sliders by site and season. Report
   only in groups, never per person, and only above a minimum count so a single
   visitor cannot be identified. Present it as *what people felt*, never as a
   health measure.
7. **FHIR R4 export.** `Observation` + `Location` per the hl7-eu/oah IG. The
   citizen answers do not have official FHIR codes yet, so define local
   CodeSystems, mark them `experimental`, and carry the same provenance fields
   already in `questions.json`. Validate the output with the HL7 validator and
   commit the validation report — judges can check it.

### Worth doing before any of the above

8. **Run the Gemini provider against real photos** using `docs/photo-sources.md`,
   and iterate on the prompt. Everything else in Phase 1 is verified; this is the
   one part that is not.
9. **Get a native speaker** to review the Portuguese, and translate the question
   set into the remaining four languages.
