# Deployment

StudyGrid ships as one container. The Node stage builds the Svelte app, and the
Python stage serves both the API and the generated static files from one origin.
No frontend API host is hard-coded.

## Security boundary

The public user-test build uses a signed HttpOnly anonymous-session cookie and
stores plans in SQLite. One browser cannot access another browser's plan, and
the UI includes a delete-my-data action. It is still a testing environment, not
a student-record system:

- There are no accounts or cross-device identity. Clearing browser cookies
  makes existing plans inaccessible until they expire.
- Use one container instance with one persistent `/data` volume. Multiple
  replicas would not share the SQLite file safely across hosts.
- Plans and activity logs expire after `PLAN_RETENTION_DAYS` and are removed
  lazily by storage operations. The default is 30 days.
- Uploaded files are processed in memory and are not retained. Extracted topics
  become part of the plan; users should still avoid confidential material.
- Do not enter personally identifiable or confidential course material.
- Keep `OPENAI_API_KEY` in the hosting provider's secret store, never in an
  image, Git commit, frontend variable, or build argument.

## Build and run

```powershell
docker build -t studygrid .
$sessionSecret = [Convert]::ToBase64String(
  [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
)
docker volume create studygrid-data
docker run --rm -p 8000:8000 `
  -e LLM_PROVIDER=fallback `
  -e SESSION_SECRET=$sessionSecret `
  -e SESSION_COOKIE_SECURE=false `
  -v studygrid-data:/data `
  studygrid
```

Open `http://127.0.0.1:8000`. The container honors the provider-assigned `PORT`
environment variable. `SESSION_COOKIE_SECURE=false` is only for this local HTTP
command; keep the production default (`true`) behind HTTPS.

For OpenAI-backed analysis and Study Coach responses, configure these runtime
variables in the hosting platform:

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=<secret>
OPENAI_MODEL=<supported model name>
OPENAI_TRANSCRIPTION_MODEL=<supported transcription model name>
SESSION_SECRET=<random secret of at least 32 bytes>
PLAN_RETENTION_DAYS=30
MATERIAL_MAX_UPLOAD_MB=25
MATERIAL_MAX_TEXT_CHARS=60000
```

When the key is missing or a provider request fails, document and webpage topic
analysis uses its deterministic fallback. Video/audio transcription requires
the key; it returns an actionable error when none is configured. `CORS_ORIGINS`
accepts a comma-separated list only when the frontend and API are intentionally
deployed on different origins. The single-container setup does not need it.

## Production smoke

The smoke check uses today's date, reads the deployment URL from the
environment, creates a temporary plan, verifies its calendar events, and then
deletes the plan.

```powershell
$env:STUDYGRID_BASE_URL='https://your-deployment.example'
.\.venv\Scripts\python.exe scripts\smoke_production.py
```

## Release checklist

- [ ] All Python smoke scripts pass.
- [ ] `npm run check`, `npm run build`, and `npx playwright test` pass.
- [ ] Container health check reports healthy.
- [ ] `/data` is a persistent volume and survives a container replacement.
- [ ] `SESSION_SECRET` is stable, secret, and `SESSION_COOKIE_SECURE=true` on HTTPS.
- [ ] `scripts/smoke_production.py` passes against the deployed URL.
- [ ] Light and dark themes are checked at desktop and phone widths.
- [ ] Keyboard-only setup, calendar selection, progress entry, and reset work.
- [ ] Provider source is visible after material analysis and coach replies.
- [ ] No secrets are present in the image, repository, logs, or browser bundle.
- [ ] User testers are told that data expires, is browser-scoped, and is not
      available across devices.

## Vercel

The repository includes a Vite build and a FastAPI ASGI function under
`api/index.py`. Import the repository in Vercel with the project root left at
the repository root; `vercel.json` supplies the install, build, output, and
same-origin routing settings.

Configure these variables for Production and Preview:

```text
ENVIRONMENT=production
SESSION_SECRET=<stable random secret of at least 32 bytes>
SESSION_COOKIE_SECURE=true
LLM_PROVIDER=fallback
```

To enable OpenAI-backed analysis and coaching, change `LLM_PROVIDER` to
`openai` and add `OPENAI_API_KEY`, `OPENAI_MODEL`, and
`OPENAI_TRANSCRIPTION_MODEL`.

Do not set `STUDYGRID_DB_PATH` on Vercel. Vercel Functions do not provide a
persistent shared filesystem, so the current fallback is intentionally
process-local and disposable there. This is suitable only for a short demo:
plans may disappear after a cold start or be unavailable on another function
instance. Durable Vercel deployment requires a managed database implementation
of `PlanRepository` before public user testing.

After deployment, run the production smoke against the assigned domain:

```powershell
$env:STUDYGRID_BASE_URL='https://your-project.vercel.app'
.\.venv\Scripts\python.exe scripts\smoke_production.py
```
