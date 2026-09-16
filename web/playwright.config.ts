import { defineConfig } from '@playwright/test'

const externalBaseURL = process.env.STUDYGRID_WEB_URL

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  reporter: 'line',
  use: {
    baseURL: externalBaseURL ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: externalBaseURL ? undefined : [
    {
      command: '.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '..',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 30_000,
      env: {
        LLM_PROVIDER: 'fallback',
        OPENAI_API_KEY: '',
      },
    },
    {
      command: 'npm run dev:vite -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: '.',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
})
