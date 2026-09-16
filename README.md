# StudyGrid

StudyGrid turns course material, exam dates, and real weekly availability into
an adaptive study calendar with spaced reviews.

## Stack

- FastAPI and Pydantic backend
- Deterministic Python scheduler
- OpenAI Responses API material analysis with an offline fallback
- Svelte 5, Vite, TypeScript, and Schedule-X frontend

## Local setup

Requirements: Python 3.14, Node.js 20 or newer, and npm.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
Copy-Item .env.example .env
Set-Location web
npm install
```

`OPENAI_API_KEY` is optional. When it is blank, material analysis uses the
deterministic fallback and the rest of the application remains functional.
`OPENAI_MODEL` defaults to `gpt-6-astra` and can be changed without touching
application code.

## Run locally

Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
Set-Location web
npm run dev
```

Open `http://127.0.0.1:5173`. The API runs at `http://127.0.0.1:8000`, and its
interactive documentation is available at `http://127.0.0.1:8000/docs`.

## Verify

Backend checks:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_ai.py
.\.venv\Scripts\python.exe scripts\smoke_scheduler.py
.\.venv\Scripts\python.exe scripts\smoke_api.py
```

Frontend checks:

```powershell
Set-Location web
npm run check
npm run build
npm run test:e2e
```

The browser test uses a locally installed Chrome browser and covers material
analysis, plan creation, calendar rendering, progress entry, adaptation, mobile
layout, and dark mode.
