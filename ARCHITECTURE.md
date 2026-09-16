# Architecture

Three layers, separated so the frontend can be built and demoed before the AI
layer exists. Each boundary is a contract, not a suggestion.

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND          web/                                     │
│  Svelte + Vite + Schedule-X (MIT)                           │
│                                                             │
│  Intake   Calendar   Session detail   Progress   Study Coach│
│                                                             │
│  Owns: rendering, local UI state, optimistic updates        │
│  Knows: the HTTP contract below. Nothing about scheduling.  │
└───────────────────────────┬─────────────────────────────────┘
                            │  JSON over HTTP
                            │  POST /api/analyze
                            │  POST /api/materials/upload|url
                            │  POST /api/plan
                            │  POST /api/progress
                            │  GET/POST/PUT/DELETE /api/activities
                            │  POST /api/chat
                            │  GET  /api/plan/latest
                            │  DELETE /api/plan/{id}
                            │  DELETE /api/session
                            │  GET  /api/privacy
                            │  GET  /api/plan/{id}/events
┌───────────────────────────┴─────────────────────────────────┐
│  BACKEND           app/                                     │
│  FastAPI                                                    │
│                                                             │
│  api/         route handlers, request/response shapes       │
│  scheduler.py deterministic placement (no AI, no I/O)       │
│  materials.py bounded document/URL/media extraction         │
│  activity.py  deterministic time-use aggregation            │
│  ai/          material analysis + coach, provider-swappable │
│  models.py    domain types shared by all of the above       │
│                                                             │
│  Owns: all scheduling logic, all AI calls, validation       │
│  Knows: nothing about HTML, CSS, or the calendar library    │
└───────────────────────────┬─────────────────────────────────┘
                            │  repository interface
┌───────────────────────────┴─────────────────────────────────┐
│  DATA              app/store/                               │
│                                                             │
│  PlanRepository  (protocol, owner-scoped)                   │
│    ├── InMemoryRepository   zero-config local development   │
│    └── SqliteRepository     public user-test persistence    │
│                                                             │
│  Owns: persistence. Nothing else.                           │
└─────────────────────────────────────────────────────────────┘
```

Every `/api` request receives a signed HttpOnly anonymous-session cookie. The
verified owner id is passed to every plan and activity repository operation; an
unknown or foreign id returns the same 404 response. SQLite stores complete
plans as versioned JSON payloads and activity logs as owner-scoped rows, so both
adaptive scheduling and Progress analytics survive a process restart.

## Why these boundaries

**The scheduler is pure.** `app/scheduler.py` takes a `PlanRequest`, returns a
`StudyPlan`. No database, no network, no clock reads beyond an injected start
date. That is why its invariants can be tested in a second, and why a live demo
produces the same calendar every time.

Subject selection uses deterministic smooth weighted round-robin. Priority and
exam urgency set each subject's weight, while a two-session streak limit
provides controlled interleaving. Topic queues remain stable and topological,
so interleaving never violates prerequisite or user-defined topic order.

`TimeAllocator` also owns recovery time. It leaves 10% of each study session
free afterward (rounded up), and when cumulative study crosses another
four-hour boundary in a day it uses the student's configurable long break
instead. Breaks constrain wall-clock placement while `_used` continues to
measure study minutes only. This keeps daily learning targets distinct from the
time the calendar must reserve for sustainable pacing.

**AI is one seam, not a layer.** Only `app/ai/` calls a model. Material analysis
and Study Coach use separate narrow provider contracts because one returns
validated topics while the other returns grounded prose. A dead API key falls
back to deterministic topic extraction and plan-derived coach answers, so the
demo still runs. Neither provider can write calendar timestamps.

**Data stays behind a protocol.** Local development can use the in-memory
implementation, while public user testing configures SQLite. Both enforce the
same owner-scoped interface, so scheduling and AI code do not know where a plan
is stored.

## Request flow: creating a plan

```
Student fills intake form
        │
        ├─ (optional) pastes text, uploads DOCX/TXT/MD/PDF/media,
        │  or enters a public URL
        │       POST /api/analyze or /api/materials/* → extract → ai/ → Topic[]
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
        ├─ record_progress()      recalculates the next review interval
        ├─ repo.save()
        ▼
{ sessions[], changes[] }   ← changes[] drives the "what moved and why" UI
```

`changes[]` exists because an adaptation the student cannot see looks like a bug.
Review sessions beyond the next retrieval are provisional. A recall result may
move, add, retain, or prune those placeholders; every outcome is summarized in
`changes[]`. All replacement slots still go through the stored `TimeAllocator`,
and the final study day before the exam is the hard upper bound.

## Request flow: Study Coach

```
Student asks about the plan, optionally with a session selected
        │
        ▼
POST /api/chat  { plan_id, message, session_id? }
        │
        ├─ repo.load(plan_id)       current plan + prior chat turns
        ├─ StudyCoach.reply()       OpenAI or deterministic fallback
        ├─ repo.save()              bounded plan-scoped history
        ▼
{ reply, history[], source, suggestions[] }
```

The coach is read-only. It can explain and recommend, but adaptation remains an
explicit `/api/progress` action handled by the scheduler.

## Request flow: Progress analytics

Completed study sessions create an idempotent `study_session` activity. Other
time is recorded manually with a broad chart category plus the student's own
label. `GET /api/activities?days=7|30` returns dense daily buckets, totals, and
recent rows; the frontend renders those values without inventing sample data.

## The HTTP contract

Frontend and backend agree on this and can then be built independently. Times
are ISO 8601 local and interpreted in each browser's timezone. Account-level
timezone synchronization remains outside the anonymous-session scope.

```
POST /api/analyze
  → { "text": "...syllabus..." , "subject": "Biology" }
  ← { "topics": [ { "name", "difficulty", "estimated_minutes", "depends_on" } ],
      "source": "ai" | "fallback" }

POST /api/materials/upload   multipart { subject, file }
POST /api/materials/url      { subject, url }
  ← topics plus material_name, material_type, extracted_chars, and truncated

GET /api/activities?days=7|30&end=YYYY-MM-DD
POST /api/activities
PUT /api/activities/{id}
DELETE /api/activities/{id}
  Owner-scoped time logs and dense chart data. Auto-synced study rows cannot be
  manually edited or deleted.

POST /api/plan
  → { "subjects": [...], "availability": {...}, "strategy": "fresh",
      "start_date": "2026-09-21" }
  ← { "plan_id", "sessions": [...], "summary", "warnings": [],
      "unscheduled": [] }

GET /api/plan/{id}/events
  ← [ { "id", "title", "start", "end", "subject", "topic",
        "repetition", "completion", "recall", "rationale" } ]
      shaped for Schedule-X directly, so the frontend does no remapping

GET /api/plan/latest
  ← the latest plan owned by this anonymous browser session, or null

POST /api/progress
  → { "plan_id", "session_id", "completion", "recall" }
  ← { "sessions": [...], "changes": [ { "type", "topic", "from", "to", "why" } ] }

POST /api/chat
  → { "plan_id", "message", "session_id"? }
  ← { "reply": { "role", "content" }, "history": [...],
      "source": "ai" | "fallback", "suggestions": [...] }

DELETE /api/plan/{id}
  ← 204 No Content
  Removes only an owned plan for a clean user-test reset.

GET /api/privacy
  ← { "anonymous_session": true, "durable_storage", "retention_days" }

DELETE /api/session
  ← 204 No Content
  Removes all plans owned by the current browser and expires its session cookie.
```

## Deployment shape

The production container builds `web/dist` and FastAPI mounts that directory
after the API routes. Frontend and API therefore share one origin and the
frontend keeps using relative `/api` URLs. Runtime configuration comes from
environment variables; no API host, plan id, exam date, or provider result is
compiled into the browser bundle.

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
      ProgressDashboard  7/30-day chart, activity form, recent activity
      StudyCoach      plan-aware read-only guidance
    App.svelte        application shell, restore/reset/privacy flow
```

`lib/api.ts` is the single point of contact with the backend. Components never
call `fetch` directly, so the mock-to-real switch happens in one place.

## Build order consequence

Because the contract is fixed, the frontend can be built against a mock
implementation of `api.ts` before any endpoint exists. That matches the stated
preference to build the frontend first.

## Non-goals for the hackathon

Named accounts, cross-device recovery, account-level timezones, real-time sync,
offline mode, and multi-region replicas. Public testers are isolated by signed
anonymous browser sessions without adding signup friction.
