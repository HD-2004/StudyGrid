# Build plan

Derived from HACKATHON.md. Ordered so that every checkpoint is demoable, and
anything cut is cut from the end.

Status legend: [x] done and verified, [ ] not started

## Phase 0 — Foundation (done)

- [x] Python 3.14 venv, FastAPI deps pinned to cp314 wheels
- [x] Domain models covering 6.1-6.6 (`app/models.py`)
- [x] Deterministic scheduler with busy blocks, dependencies, three strategies
- [x] Progress feedback loop: recall quality adjusts future reviews
- [x] Invariant smoke check (`scripts/smoke_scheduler.py`)

## Phase 1 — API surface (done)

- [x] Layer separation: `app/api/`, `app/scheduler.py`, `app/store/`
- [x] `POST /api/plan` — build a plan from subjects + availability
- [x] `POST /api/progress` — record completion + recall, return adapted plan
- [x] `GET /api/plan/{id}/events` — Schedule-X shaped, no frontend remapping
- [x] `PlanRepository` protocol + in-memory implementation
- [x] Stable session ids, so the UI can reference sessions across adaptations
- [x] `changes[]` in the progress response, so adaptation is visible
- [x] API smoke test (`scripts/smoke_api.py`), server boot verified

Checkpoint reached: full CREATE -> ADAPT loop over HTTP, no UI.

## Phase 2 — AI material analysis (done)

- [x] `LLMProvider` protocol: one method, syllabus text -> validated `Topic` list
- [x] OpenAI Responses API provider using Pydantic Structured Outputs
- [x] Live OpenAI analysis verified with `source: "ai"`
- [x] Deterministic fallback so the demo survives an API outage or dead key
- [x] `POST /api/analyze` — paste syllabus text, get topics back
- [x] Offline AI smoke check (`scripts/smoke_ai.py`)

Checkpoint: paste a syllabus, get topics with difficulty and time estimates.

Note: the LLM decides *what* to study; the scheduler decides *when*. Models that
emit wall-clock times produce overlapping slots.

## Phase 2.5 — Frontend (done)

Buildable now: the HTTP contract is fixed and verified, so `lib/api.ts` can be
mocked and swapped for real calls with no component changes.

- [x] Vite + Svelte scaffold in `web/`
- [x] `lib/types.ts` mirroring the contract, `lib/api.ts` as the only fetch site
- [x] Schedule-X calendar rendering `/api/plan/{id}/events`
- [x] Intake form: subjects, exam dates, availability, fixed commitments
- [x] Session detail: completion + recall entry
- [x] ChangeLog panel rendering `changes[]`
- [x] Visual distinction between first passes and reviews
- [x] Light/dark themes, responsive mobile layout, and full UI states
- [x] Calendar-first Material 3 redesign inspired by Google Calendar
- [x] Browser test for ANALYZE -> CREATE -> ADAPT (`web/tests/app.spec.ts`)

Checkpoint: end-to-end demo in a browser.

## Phase 4 — Demo polish (prepared, next)

- [x] Keep the calendar interactive on first load; setup opens only on request
- [x] Make adaptation visible: show what moved and why
- [x] Empty and over-capacity states worded honestly
- [x] Mobile and dark-mode browser checks
- [ ] Add three one-click judge presets: fresh start, mid-semester, exam rush
- [ ] Show whether material analysis used OpenAI or the offline fallback
- [ ] Add a short guided demo path with a reliable reset action
- [ ] Run a keyboard and screen-reader pass on the complete judge flow
- [ ] Prepare deployment configuration and a production smoke checklist

## Phase 5 — If time remains

- [ ] SQLite persistence
- [ ] File upload (PDF/DOCX) instead of pasted text
- [ ] Concept relationship graph
- [ ] Pitch deck via the `pptx` skill

## Cut list, in order

Persistence, file upload, the concept graph, and multi-user accounts. The demo
works without all four.

## Open decisions

1. Sections 10, 11, and 12 of HACKATHON.md are empty and are judged
