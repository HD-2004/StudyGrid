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

## Phase 3 — Time-use insights (done, HACKATHON.md 8.3)

- [x] `MissReason` enum with labels served from the backend
- [x] Miss reason captured on partial and missed sessions
- [x] `plan.history` append-only outcome log, so rescheduling cannot erase a miss
- [x] `app/insights.py` aggregation: counts, reason ranking, weak weekdays
- [x] Withholds pattern claims below 5 logged sessions
- [x] `GET /api/plan/{id}/insights` and `GET /api/miss-reasons`
- [x] Reason chips in session detail, shown only when time was lost
- [x] Insights panel with lost-time attribution
- [x] Tests: `scripts/smoke_insights.py`, plus browser coverage in `smoke_ui.py`

## Phase 4 — Demo polish (done and verified)

- [x] Adaptive expanding review intervals driven by recall and exam deadline
- [x] Priority-weighted controlled interleaving with prerequisite-safe ordering
- [x] Session presets/custom duration, 10% recovery, and configurable long break after four hours
- [x] Daily availability in hours with weekly summary and unusable-day warning
- [x] Plan-aware Study Coach with persisted history and deterministic fallback
- [x] Keep the calendar interactive on first load; setup opens only on request
- [x] Make adaptation visible: show what moved and why
- [x] Empty and over-capacity states worded honestly
- [x] Mobile and dark-mode browser checks
- [x] Replace one-click starting-point presets with editable dates, daily study
      windows, capacity, and fixed commitments from the real user
- [x] Show whether material analysis used OpenAI or the offline fallback
- [x] Add a short guided demo path with a reliable backend reset action
- [x] Run keyboard, accessible-name, and automated WCAG A/AA checks on the judge flow
- [x] Prepare single-container deployment configuration and a production smoke checklist

## Phase 5A — Public user-test readiness (done and verified)

- [x] Capture product strategy and accessibility intent in `PRODUCT.md`
- [x] SQLite persistence with schema versioning and configurable retention
- [x] Signed HttpOnly anonymous browser sessions
- [x] Enforce plan ownership on read, update, chat, insights, and delete routes
- [x] Restore the latest owned plan after a browser reload
- [x] Add delete-my-data controls and a dynamic retention notice
- [x] Persist `/data` in the production container and require `SESSION_SECRET`
- [x] Add security headers and multi-user persistence smoke coverage

Checkpoint: one public deployment can serve independent anonymous testers
without exposing plans across browsers or losing all data on every restart.

## Phase 5B — If time remains

- [x] DOCX, TXT, Markdown, and PDF upload with bounded extraction
- [x] Public URL ingestion with private-network/SSRF blocking
- [x] Video/audio transcription when an OpenAI key is configured
- [x] Progress analytics with 7/30-day charts and owner-scoped activity logs
- [x] Custom planning date, daily window, capacity, and fixed commitments
- [ ] Concept relationship graph
- [ ] Pitch deck via the `pptx` skill

## Phase 6 — Health-aware planning (in progress)

Product boundary: this feature gives general wellness and workload guidance; it
does not diagnose illness or replace medical advice. Health data stays scoped to
the same anonymous owner as the study plan, and raw heart-rate samples are not
stored.

### Phase 6A — Health domain and private sync API

- [ ] Add Health Connect connection, daily summary, and readiness models
- [ ] Pair the browser with one Android companion using a short-lived code
- [ ] Accept sleep, resting-heart-rate, and optional HRV daily summaries
- [ ] Store only daily aggregates with source and last-sync metadata
- [ ] Support pause, disconnect, and delete-health-data controls

### Phase 6B — Readiness engine

- [ ] Build a personal 7-day baseline when enough history is available
- [ ] Return one of: insufficient data, ready, reduce load, or recovery
- [ ] Explain every status using sleep/heart-rate/HRV factors and confidence
- [ ] Keep thresholds and capacity multipliers configurable on the backend
- [ ] Keep deadline risk and explicit task priority as hard scheduling constraints

### Phase 6C — Progress dashboard and calendar signal

- [ ] Add health/readiness cards and 7/30-day charts only to Progress
- [ ] Show a compact today's-readiness badge in Calendar
- [ ] Add Health Connect pairing, sync metadata, check-in, pause, and delete UI
- [ ] Show schedule recommendations before the user applies any change
- [ ] Preserve responsive, keyboard, dark-theme, and empty/error states

### Phase 6D — Health-aware schedule adaptation

- [ ] Protect overdue, near-deadline, high-priority, and prerequisite work
- [ ] On lower-readiness days, shorten/split flexible blocks and add recovery gaps
- [ ] Move only lower-priority work and keep unscheduled remainders visible
- [ ] Require confirmation before exceeding capacity or applying health changes
- [ ] Record every health-driven change for Progress analytics and explanation

### Phase 6E — Android Health Connect companion

- [ ] Create a Kotlin/Jetpack Compose companion for Android 9+
- [ ] Request Health Connect permissions with an explicit disclosure screen
- [ ] Sync sleep sessions, resting heart rate, and HRV when the device provides it
- [ ] Pair by one-time code without exposing the browser session cookie
- [ ] Support manual sync, background sync, revocation, and clear error states

Phase 6 acceptance checkpoint: an Android tester can pair one device, sync daily
health aggregates, see an explainable readiness state in Progress, preview a
deadline-safe lighter schedule, and explicitly apply it without losing work.

## Cut list, in order

The concept graph, named/cross-device accounts, and the pitch deck. The public
user-test flow works without all three.

## Open decisions

1. Anonymous sessions isolate public testers but do not provide named accounts
   or cross-device recovery. The Android companion therefore pairs to one
   anonymous plan with a revocable token for the MVP.
2. Health Connect is the only wearable ecosystem in Phase 6. Apple Health and
   direct vendor integrations remain out of scope until the Android flow is
   validated.
3. Decide whether the concept graph or pitch polish creates more judging value.
4. The current worktree still needs a reviewed commit before deployment.
