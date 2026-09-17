import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

const apiTarget = process.env.STUDYGRID_API_TARGET ?? 'http://127.0.0.1:8001'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    // The FastAPI backend also allows this origin via CORS. The proxy means
    // the frontend can use relative /api paths and never hardcode a host.
    proxy: {
      '/api': apiTarget,
    },
  },
})
