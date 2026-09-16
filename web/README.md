# StudyGrid frontend

Svelte 5 and Vite client for the StudyGrid planning API.

```powershell
npm install
npm run dev
```

`npm run dev` starts both FastAPI and Vite, waits for the API health check, and
then opens the frontend on `http://127.0.0.1:5173`. Vite proxies `/api`
requests to `http://127.0.0.1:8000`.

Use `npm run dev:vite` only when the API is already running in another
terminal.

Verification commands:

```powershell
npm run check
npm run build
```

The end-to-end browser workflow lives at `../scripts/smoke_ui.py` and expects
the API and frontend dev servers to be running.
