# StudyGrid

StudyGrid turns course material, exam dates, and real daily availability into
an adaptive study calendar with spaced reviews.

## Stack

- FastAPI and Pydantic backend
- Deterministic Python scheduler
- SQLite persistence with signed anonymous browser-session isolation
- OpenAI Responses API material analysis and Study Coach, both with offline fallbacks
- DOCX, TXT, Markdown, PDF, public-URL, and video/audio material ingestion
- Progress charts for study, work, entertainment, illness, unexpected events,
  rest, and custom labels
- Svelte 5, Vite, TypeScript, and Schedule-X frontend
- Project-local LearnHarness design workflow and deterministic UI detector

## Local setup

Requirements: Python 3.14, Node.js 20 or newer, and npm.

The StudyGrid app builds on Node.js 20+. The optional `fk-skills` installer
currently declares Node.js 24+ for reinstalling or updating the project-local
LearnHarness workflow; the installed files do not become a browser dependency.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
Set-Location web
npm install
```

`OPENAI_API_KEY` is optional. When it is blank, material analysis and the
plan-aware Study Coach use deterministic fallbacks and the application remains functional.
`OPENAI_MODEL` defaults to `gpt-6-astra` and can be changed without touching
application code.

DOCX, TXT, Markdown, PDF, and webpage extraction work without an AI key; topic
analysis then uses the deterministic fallback. Video/audio transcription needs
`OPENAI_API_KEY` and uses `OPENAI_TRANSCRIPTION_MODEL`. Raw files are processed
in memory and are not retained. The default upload limit is 25 MB.

The sample `.env` enables local SQLite persistence at `data/studygrid.db`.
`SESSION_SECRET` may be blank for disposable development, but public user-test
deployments must provide a stable random secret so browser sessions survive a
server restart.

## Run locally

Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
npm run dev -- --port 5173
```

The repository-level npm scripts forward to the frontend package in `web`, so
run them from the repository root. Running directly inside `web` is also
supported with `npm run dev -- --port 5173`.

Open `http://127.0.0.1:5173`. The API runs at `http://127.0.0.1:8000`, and its
interactive documentation is available at `http://127.0.0.1:8000/docs`.

## Verify

Backend checks:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_ai.py
.\.venv\Scripts\python.exe scripts\smoke_coach.py
.\.venv\Scripts\python.exe scripts\smoke_scheduler.py
.\.venv\Scripts\python.exe scripts\smoke_api.py
.\.venv\Scripts\python.exe scripts\smoke_insights.py
.\.venv\Scripts\python.exe scripts\smoke_persistence.py
.\.venv\Scripts\python.exe scripts\smoke_materials.py
.\.venv\Scripts\python.exe scripts\smoke_activities.py
```

Frontend checks:

```powershell
Set-Location web
npm run check
npm run build
npx playwright test
```

With both local servers running, run the browser workflow from the repository
root:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_ui.py
```

The browser test covers plan creation, calendar rendering, Study Coach,
progress entry, adaptation, time-use insights, reset, dark mode, mobile layout,
keyboard behavior, and automated WCAG A/AA checks.

## Deploy for user testing

The repository includes a multi-stage `Dockerfile` that builds the Svelte app
and serves it with FastAPI from one origin. Read `DEPLOYMENT.md` before hosting:
the anonymous session model is designed for public user testing, not permanent
student records or cross-device accounts.
