# CLAUDE.md — StreamLens

Guidance for Claude Code (and any contributor) working in this repository.

---

## 1. The brief

**StreamLens** — IEEE OneAquaHealth Global Hackathon 2026 (deadline: 1 Oct 2026, 09:30 IST).

OneAquaHealth is an EU project on urban stream health and One Health (ecosystem +
human health), running in five research cities: **Coimbra, Benevento, Toulouse,
Ghent, Oslo**. Its Citizen Science App lets citizens assess streams (channel form,
bed and banks, habitats, natural debris, flow, water appearance, water abstraction,
barriers, polluted pipes, sewage, works, left/right margins: paving, plant cover,
dominant plants, invasive plants, cuts), give an overall **Good / Moderate / Poor**
rating, record emotions (joy, serenity, anger, fear), and upload upstream and
downstream photos.

StreamLens is one loop with three parts:

### 1. OBSERVE — main feature (Track 1 Citizen Science UX + Track 3 AI with human decision)
Photo-first guided assessment. A vision model pre-fills answers to the real app's
questions as **suggestion chips** carrying a confidence level and a short reason.
The citizen confirms or rejects every suggestion. **AI never sets the final rating.**
Plain-language glossary with a simple explanation for every ecology term.
Multilingual (en, pt, it, fr, nl, no). Live quality checks (blurry or dark photo,
GPS far from the site, answer contradicts the photo). Offline-first PWA.

### 2. UNDERSTAND & ACT (Track 6 / 2)
Stream health card; a rule-based 48-hour alert (Open-Meteo rain/heat + recent
sewage/stagnation reports) that shows its reasons; and a table linking observed
problems to restoration measures from the OneAquaHealth catalogue, with health
benefits.

### 3. RETURN (Track 5 / 4)
Quests aimed at data gaps (sites not visited recently, after-rain checks, missing
seasons); points for good photos and for answers that agree with other visitors;
a team leaderboard; and a wellbeing mirror built from the emotion data.

Plus: **FHIR R4 export** (Observation + Location) following the hl7-eu/oah
Implementation Guide.

---

## 2. Non-negotiable rules

These are product ethics, not style preferences. Do not relax them for convenience.

1. **AI suggests, humans decide.** Every AI output is a *suggestion* the citizen
   must confirm or reject. The AI must never set, default, or pre-select the
   overall Good/Moderate/Poor rating. The submitted record stores the citizen's
   answer, and separately what the AI had suggested — never the AI answer alone.
2. **Never claim medical diagnosis.** StreamLens talks about ecosystem health and
   *potential* human-health relevance in general, cautious terms. No diagnosis, no
   individual health advice, no "this water will make you ill".
3. **Label synthetic data.** Every demo, seed or generated record carries
   `"synthetic": true`. The judges are scientists; they must be able to tell real
   observations from fixtures at a glance.
4. **Keep the Observe flow polished above everything else.** If time is short, a
   working end-to-end Observe slice (site → photos → chips → confirm → submit →
   saved) beats every other feature. Polish that first, then widen.
5. **Provenance is visible.** Never present an answer code as official unless it
   came from a public source. Each question and option carries a `source` field.
   Non-English strings that were machine translated carry `"machine_translated": true`.
6. **When the mock AI provider is active, the UI says so** — a "demo AI (mock)"
   badge. The demo must never look like it is running a real model when it is not.
7. **Privacy by default.** EXIF metadata (including embedded GPS) is stripped from
   every uploaded photo before it is saved. Location is stored only in its own
   explicit field, from an explicit user action. Images are downscaled to
   `MAX_IMAGE_PX` (1600 px) on the long edge.
8. **Secrets live only in `.env`.** Never commit a key. `.env.example` documents
   every variable.

---

## 3. Architecture

```
/api     FastAPI (Python 3.11) + Pydantic v2 + SQLModel/SQLite
  app/
    main.py            app factory, CORS, router mounting
    config.py          pydantic-settings, reads .env
    models.py          SQLModel tables (Observation, Answer, Photo)
    schemas.py         Pydantic request/response models
    questions.py       loads /data/questions.json, validates answer codes
    sites.py           loads /data/sites.json (local file, never the live API)
    imaging.py         EXIF strip, resize, blur (variance of Laplacian), brightness
    ai/
      base.py          VisionProvider protocol + Suggestion dataclass
      mock.py          MockProvider — deterministic, no network, used when no key
      gemini.py        GeminiProvider — google-genai, structured JSON output
      factory.py       picks a provider from settings
      prompts/
        assess_v1.md   the vision prompt, loaded at runtime
    routers/
      health.py  sites.py  questions.py  assess.py  observations.py
  tests/               pytest

/web     React + Vite + TypeScript + Tailwind + vite-plugin-pwa
  src/
    screens/           Site → Photos → Review → Rating → Submit
    components/        Chip, GlossaryTerm, QualityBanner, MockBadge...
    lib/api.ts         API client
    lib/db.ts          Dexie/IndexedDB outbox
    lib/sync.ts        flush the outbox when back online
    i18n/              en, pt, it, fr, nl, no

/data    sites.json (from the real ENORA API, fetched once), questions.json
/docs    notes, photo test sources, FHIR mapping
/scripts fetch_sites.py, dev.ps1
```

**Data flow (Observe):** site pick → 2 photos → `POST /assess/suggest` (multipart)
→ chips + photo-quality report → citizen confirms/edits each chip → citizen picks
rating + emotions → `POST /observations`. Offline, the submit is queued in
IndexedDB and flushed on reconnect.

---

## 4. Data sources

- **Sites:** `https://api.enora-oah.eu/api/sites/all` — public, no auth. 106 sites
  (Toulouse 24, Ghent 22, Coimbra 20, Benevento 20, Oslo 20). Fetched **once** into
  `/data/sites.json` by `scripts/fetch_sites.py` and served from that local file at
  runtime — the app must work offline and must not depend on the live API.
  Attribution: **"Site data: OneAquaHealth / ENORA API"**.
- **Questions:** `https://api.enora-oah.eu/api/citizens/*` requires authentication
  (returns 401), so `/data/questions.json` is reconstructed by hand from the
  published OneAquaHealth Citizen Science App categories and marked
  `"source": "manual"` per question and per option.
- **Weather:** Open-Meteo (no key).

---

## 5. Commands

```powershell
# One-shot dev (both apps)
npm install            # root, installs concurrently
npm run dev            # API on :8000, web on :5173

# API only
py -3.11 -m venv api/.venv
api/.venv/Scripts/python -m pip install -r api/requirements.txt
api/.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # from /api
api/.venv/Scripts/python -m pytest api/tests -q

# Web only
cd web && npm install && npm run dev
cd web && npm run test        # vitest
cd web && npm run build
```

---

## 6. Conventions

- Python: type hints everywhere, Pydantic v2 (`model_validate`, not `parse_obj`).
- TypeScript: `strict`. No `any` in application code.
- Tests must never hit the network: the AI provider is mocked, sites and questions
  come from `/data`.
- Accessibility: tap targets ≥ 44 px, WCAG AA contrast, every control labelled,
  focus visible. The flow must be usable one-handed outdoors in sunlight.
- Commit after each major step, with a message that says what changed and why.
