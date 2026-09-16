# StudyGrid

AI study planner: a calendar that generates and adapts study schedules.

Hackathon project, 48-hour build window. Repo: https://github.com/HD-2004/StudyGrid

## Core idea

Student enters subjects, exam dates, and available time. The AI produces a
concrete study schedule laid out on a calendar, then adapts it when sessions
get missed or deadlines move.

## Priorities under deadline

1. AI plan generation working end to end, even if rough
2. Calendar rendering the generated plan
3. Adaptive rescheduling when a session is skipped
4. Polish and persistence last

The AI scheduling logic is the differentiator. The calendar is a means of
displaying it. When time is short, cut calendar features, not scheduling
quality.

## Licensing rule

Only build on dependencies with an explicit permissive license (MIT, Apache-2.0,
BSD). A public GitHub repo with no LICENSE file grants no right to copy, modify,
or distribute; default copyright applies. Verify a license before adopting any
source.

Rejected: Opisek/luna (no license file, unlicensed).

## Stack

Python 3.14 + FastAPI backend. Schedule-X (MIT) for the calendar UI.
OpenAI Responses API for material analysis, with a deterministic fallback.

Python 3.14 is new: always install with `--only-binary=:all:`. Older pins of
pydantic force a source build of pydantic-core, which needs the MSVC linker and
fails on this machine (no Visual Studio build tools).

## Architecture

The LLM decides *what* to study: breaking a syllabus into topics, tagging
difficulty, estimating minutes. The deterministic scheduler in `app/scheduler.py`
decides *when*. Models emitting wall-clock times produce overlapping and
out-of-bounds slots, so placement stays in Python. It is also reproducible,
which matters when demoing live.

All slot placement must go through a single `TimeAllocator`. Two allocators over
the same calendar hand out the same slot twice (this bug already happened once).

Any AI call needs a deterministic fallback. A dead API key must not break the
demo.

## Layer separation

```
web/          frontend, Svelte + Schedule-X. Knows the HTTP contract only.
app/api/      route handlers, wire schemas. No scheduling logic.
app/scheduler.py  pure placement. No I/O, no AI, no clock reads.
app/ai/       the only place a model is called.
app/store/    persistence behind PlanRepository. Nothing else.
```

Rules that keep the separation real:
- Components never call `fetch`; only `web/src/lib/api.ts` does.
- Handlers never compute times; they call the scheduler.
- Callers depend on `PlanRepository`, never on a concrete store.
- `app/api/schemas.py` holds wire shapes, `app/models.py` holds domain types.
  Keeping them separate means the domain can change without breaking the UI.

See `ARCHITECTURE.md` for the diagrams and the full contract.

## Source of truth

`HACKATHON.md` is the spec. `PLAN.md` is the phased build order and cut list.
`ARCHITECTURE.md` is the layer contract.

All smoke tests must pass after any backend change:
```
.venv\Scripts\python.exe scripts\smoke_ai.py
.venv\Scripts\python.exe scripts\smoke_scheduler.py
.venv\Scripts\python.exe scripts\smoke_api.py
```
They assert provider fallback and validation, no overlaps, no collisions with
fixed commitments, nothing past an exam date, budgets respected, and that
adaptations persist.

## Commands

```
.venv\Scripts\python.exe scripts\smoke_ai.py             # verify material analysis
.venv\Scripts\python.exe scripts\smoke_scheduler.py      # verify scheduler
.venv\Scripts\python.exe -m uvicorn app.main:app --reload  # dev server
.venv\Scripts\python.exe -m pip install --only-binary=:all: <pkg>
```
