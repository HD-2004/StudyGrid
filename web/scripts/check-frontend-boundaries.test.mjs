import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { analyzeSource, checkFrontendBoundaries } from './check-frontend-boundaries.mjs'

test('allows the canonical API fetch and ignores comments and strings', () => {
  assert.deepEqual(analyzeSource('src/lib/api.ts', 'export const request = () => fetch("/api/plan")'), [])
  assert.deepEqual(analyzeSource('src/view.ts', '// fetch("/api")\nconst note = "TimeAllocator autoSchedule"'), [])
})

test('rejects every frontend fetch reference outside lib/api.ts', () => {
  assert.match(analyzeSource('src/App.svelte', 'const send = fetch')[0], /fetch reference/)
  assert.match(analyzeSource('src/view.ts', 'window.fetch("/api")')[0], /fetch reference/)
})

test('rejects frontend allocators and automatic-placement helpers', () => {
  assert.match(analyzeSource('src/schedule.ts', 'class BrowserAllocator {}')[0], /allocator/)
  assert.match(analyzeSource('src/schedule.ts', 'function findSuggestedMove() {}')[0], /automatic placement/)
  assert.match(analyzeSource('src/schedule.ts', 'const computeSuggestedTime = () => null')[0], /slot-search/)
  assert.match(analyzeSource('src/schedule.ts', 'const preview = new AiPreview()')[0], /legacy AI placement/)
})

test('requires the canonical API client to retain the only fetch call', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'studygrid-boundaries-'))
  const srcRoot = path.join(root, 'src')
  await mkdir(path.join(srcRoot, 'lib'), { recursive: true })
  await writeFile(path.join(srcRoot, 'lib', 'api.ts'), 'export const request = () => null')
  try {
    assert.deepEqual(await checkFrontendBoundaries(srcRoot), ['src/lib/api.ts: canonical fetch call is missing'])
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
