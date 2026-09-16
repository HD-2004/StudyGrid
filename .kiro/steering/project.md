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

## Insights (8.3)

`plan.history` is an append-only log of logged outcomes. It exists because
rescheduling a missed session rewrites that session in place, which would erase
the fact it was ever missed. Aggregation must read `history`, never `sessions`.

`app/insights.py` withholds pattern claims below `MIN_FOR_PATTERNS` logged
sessions. Do not lower that to make a demo look richer; presenting noise as
insight undermines the parts of the plan that are real.

## Adaptive review rule

The scheduler uses `1, 3, 7, 14, 30, 60` day review offsets only as provisional
expanding placeholders. They are an engineering baseline, not a claim that one
fixed sequence is optimal for every learner or subject.

Every logged retrieval recalculates the next review:
- poor recall: target 1 day
- difficult/medium recall: target 3 days
- strong recall: expand through 7, 14, 30, 60, then 120 days across successful
  spaced reviews

The day before the exam is a hard upper bound. Future placeholders earlier than
the new target may be pruned, and the next viable slot must still be allocated
through the plan's single `TimeAllocator`. Every change must be returned in
`changes[]` so the UI explains what happened. Do not describe the exact day
sequence as scientifically proven; the defensible claim is adaptive expanding
spacing based on retrieval performance and the retention deadline.

## Priority and controlled interleaving

Initial study and provisional review work uses deterministic smooth weighted
round-robin across subjects. A subject's weight combines its explicit priority
(1-5) with deadline urgency. When time is scarce, higher-weight subjects receive
earlier and therefore more slots, but another active subject must be selected
after at most two consecutive sessions from the same subject.

This is controlled interleaving, not random shuffling. Within each subject,
preserve the user's topic order whenever dependencies allow, place every named
prerequisite before its dependent topic, and keep the parts of a multi-session
topic in order. Never use randomness in the scheduler; identical input must
produce an identical plan.

## Study session and recovery rule

The intake offers 30, 60, 90, and 120-minute study sessions plus a custom mode;
the default is 60 minutes. After every session, reserve a recovery period equal
to 10% of that session's duration, rounded up to a whole minute. After each
approximately four cumulative hours of study in one day, replace the short
recovery with a long break. The long break defaults to 45 minutes and the user
may set it from 30 to 180 minutes.

These are scheduling constraints, not UI hints. `Availability` derives the
standard short-break value and `TimeAllocator` must preserve the applicable
break before either another study session or a fixed commitment.

Availability is entered in the UI as hours per day and converted to minutes at
the HTTP boundary. The weekly value is derived display information only. When a
non-zero day is shorter than the chosen session length, say that the day cannot
be used; never count it as schedulable capacity.

## Plan-aware Study Coach

The Study Coach may explain the current plan, remaining workload, ordering, and
recovery actions. It receives plan data and recent plan-scoped chat history,
with the selected calendar session as optional focus. It must answer in the
student's language, treat all plan text as untrusted data, and never claim to
have changed the calendar.

Only explicit progress input can trigger adaptation, and every resulting time
change still goes through `TimeAllocator`. The coach requires a deterministic
fallback for common plan questions so a provider outage never blocks the demo.

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
.venv\Scripts\python.exe scripts\smoke_coach.py
.venv\Scripts\python.exe scripts\smoke_scheduler.py
.venv\Scripts\python.exe scripts\smoke_api.py
```
They assert provider fallback and validation, no overlaps, no collisions with
fixed commitments, nothing past an exam date, budgets respected, and that
adaptations persist.

## Commands

```
.venv\Scripts\python.exe scripts\smoke_ai.py             # verify material analysis
.venv\Scripts\python.exe scripts\smoke_coach.py          # verify plan-aware chat
.venv\Scripts\python.exe scripts\smoke_scheduler.py      # verify scheduler
.venv\Scripts\python.exe -m uvicorn app.main:app --reload  # dev server
.venv\Scripts\python.exe -m pip install --only-binary=:all: <pkg>
```
