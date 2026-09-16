# StudyGrid frontend

Svelte 5 and Vite client for the StudyGrid planning API.

```powershell
npm install
npm run dev
```

During development, Vite proxies `/api` requests to
`http://127.0.0.1:8000`.

Verification commands:

```powershell
npm run check
npm run build
```

The end-to-end browser workflow lives at `../scripts/smoke_ui.py` and expects
the API and frontend dev servers to be running.
