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

## Phase 2 — AI material analysis (~3h, 6.1)

- [ ] `LLMProvider` protocol: one method, syllabus text -> validated `Topic` list
- [ ] One concrete provider (pending your decision), structured output
- [ ] Deterministic fallback so the demo survives an API outage or dead key
- [ ] `POST /api/analyze` — paste syllabus text, get topics back

Checkpoint: paste a syllabus, get topics with difficulty and time estimates.

Note: the LLM decides *what* to study; the scheduler decides *when*. Models that
emit wall-clock times produce overlapping slots.

## Phase 2.5 — Frontend (moved earlier at your request, ~5h)

Buildable now: the HTTP contract is fixed and verified, so `lib/api.ts` can be
mocked and swapped for real calls with no component changes.

- [ ] Vite + Svelte scaffold in `web/`
- [ ] `lib/types.ts` mirroring the contract, `lib/api.ts` as the only fetch site
- [ ] Schedule-X calendar rendering `/api/plan/{id}/events`
- [ ] Intake form: subjects, exam dates, availability, fixed commitments
- [ ] Session detail: completion + recall entry
- [ ] ChangeLog panel rendering `changes[]`
- [ ] Visual distinction between first passes and reviews

Checkpoint: end-to-end demo in a browser.

## Phase 4 — Demo polish (~3h, sections 11-12)

- [ ] Seed data for all three entry points, loadable in one click
- [ ] Make adaptation visible: show what moved and why
- [ ] Empty and over-capacity states worded honestly
- [ ] Mobile layout check (judges use phones)

## Phase 5 — If time remains

- [ ] SQLite persistence
- [ ] File upload (PDF/DOCX) instead of pasted text
- [ ] Concept relationship graph
- [ ] Pitch deck via the `pptx` skill

## Cut list, in order

Persistence, file upload, the concept graph, and multi-user accounts. The demo
works without all four.

## Open decisions

1. LLM provider — blocks Phase 2
2. Sections 9, 10, 11, 12 of HACKATHON.md are empty and are judged
