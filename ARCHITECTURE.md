# Architecture

Three layers, separated so the frontend can be built and demoed before the AI
layer exists. Each boundary is a contract, not a suggestion.

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND          web/                                     │
│  Svelte + Vite + Schedule-X (MIT)                           │
│                                                             │
│  Intake form   Calendar view   Session detail   Progress    │
│                                                             │
│  Owns: rendering, local UI state, optimistic updates        │
│  Knows: the HTTP contract below. Nothing about scheduling.  │
└───────────────────────────┬─────────────────────────────────┘
                            │  JSON over HTTP
                            │  POST /api/analyze
                            │  POST /api/plan
                            │  POST /api/progress
                            │  GET  /api/plan/{id}/events
┌───────────────────────────┴─────────────────────────────────┐
│  BACKEND           app/                                     │
│  FastAPI                                                    │
│                                                             │
│  api/         route handlers, request/response shapes       │
│  scheduler.py deterministic placement (no AI, no I/O)       │
│  ai/          material analysis, provider-swappable         │
│  models.py    domain types shared by all of the above       │
│                                                             │
│  Owns: all scheduling logic, all AI calls, validation       │
│  Knows: nothing about HTML, CSS, or the calendar library    │
└───────────────────────────┬─────────────────────────────────┘
                            │  repository interface
┌───────────────────────────┴─────────────────────────────────┐
│  DATA              app/store/                               │
│                                                             │
│  PlanRepository  (protocol)                                 │
│    ├── InMemoryRepository   default, hackathon demo         │
│    └── SqliteRepository     added only if time permits      │
│                                                             │
│  Owns: persistence. Nothing else.                           │
└─────────────────────────────────────────────────────────────┘
```

## Why these boundaries

**The scheduler is pure.** `app/scheduler.py` takes a `PlanRequest`, returns a
`StudyPlan`. No database, no network, no clock reads beyond an injected start
date. That is why its invariants can be tested in a second, and why a live demo
produces the same calendar every time.

**AI is one seam, not a layer.** Only `app/ai/` calls a model, and only to turn
material into topics. Every provider sits behind one protocol with one method.
Swapping Claude for Gemini touches one file. A dead API key falls back to a
deterministic analyzer, so the demo still runs.

**Data is a protocol from the start.** The in-memory store ships first because
persistence is on the cut list. When SQLite arrives it satisfies the same
interface and nothing above it changes.

## Request flow: creating a plan

```
Student fills intake form
        │
        ├─ (optional) pastes syllabus text
        │       POST /api/analyze  →  ai/  →  Topic[]
        │       fallback: heuristic split if the model is unavailable
        │
        ▼
POST /api/plan  { subjects, availability, strategy }
        │
        ├─ validate            pydantic, at the boundary
        ├─ build_plan()        scheduler, deterministic
        ├─ repo.save()         data layer
        ▼
{ plan_id, sessions[], summary, warnings[], unscheduled[] }
        │
        ▼
Calendar renders sessions. Warnings and unscheduled work are shown, not hidden.
```

## Request flow: adapting a plan

This is the differentiator, so it gets its own path.

```
Student clicks a session, reports completion + recall
        │
        ▼
POST /api/progress  { plan_id, session_id, completion, recall }
        │
        ├─ repo.load(plan_id)
        ├─ record_progress()      may move work, may add a review
        ├─ repo.save()
        ▼
{ sessions[], changes[] }   ← changes[] drives the "what moved and why" UI
```

`changes[]` exists because an adaptation the student cannot see looks like a bug.

## The HTTP contract

Frontend and backend agree on this and can then be built independently. Times
are ISO 8601 local, no timezone conversion (single-user demo scope).

```
POST /api/analyze
  → { "text": "...syllabus..." , "subject": "Biology" }
  ← { "topics": [ { "name", "difficulty", "estimated_minutes", "depends_on" } ],
      "source": "ai" | "fallback" }

POST /api/plan
  → { "subjects": [...], "availability": {...}, "strategy": "fresh",
      "start_date": "2026-09-21" }
  ← { "plan_id", "sessions": [...], "summary", "warnings": [],
      "unscheduled": [] }

GET /api/plan/{id}/events
  ← [ { "id", "title", "start", "end", "subject", "topic",
        "repetition", "completion", "recall", "rationale" } ]
      shaped for Schedule-X directly, so the frontend does no remapping

POST /api/progress
  → { "plan_id", "session_id", "completion", "recall" }
  ← { "sessions": [...], "changes": [ { "type", "topic", "from", "to", "why" } ] }
```

## Frontend structure

```
web/
  src/
    lib/
      api.ts          the only file that talks HTTP
      types.ts        mirrors the contract above
    components/
      IntakeForm      subjects, exam dates, availability, fixed commitments
      Calendar        Schedule-X wrapper
      SessionDetail   completion + recall entry
      ChangeLog       renders changes[] so adaptation is visible
    routes/
      +page.svelte
```

`lib/api.ts` is the single point of contact with the backend. Components never
call `fetch` directly, so the mock-to-real switch happens in one place.

## Build order consequence

Because the contract is fixed, the frontend can be built against a mock
implementation of `api.ts` before any endpoint exists. That matches the stated
preference to build the frontend first.

## Non-goals for the hackathon

Multi-user accounts, auth, timezones, real-time sync, offline mode. Single user,
single browser, one session. Adding auth to a demo nobody logs into costs hours
and shows judges nothing.
