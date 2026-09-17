import { expect, test, type Browser, type Page, type Route } from '@playwright/test'
import { readdirSync, readFileSync } from 'node:fs'
import { extname, join, relative, resolve } from 'node:path'
import type { CalendarEvent, PlanResponse, StudySession } from '../src/lib/types'

type ProviderSource = 'ai' | 'fallback'
type Authority = 'manual' | 'scheduler'
type RenderedEvent = { id: string; start: string; end: string }

type Scenario = {
  index: number
  source: ProviderSource
  authority: Authority
  coachReply: string
  initial: CalendarEvent[]
  authoritative: CalendarEvent[]
}

const SEED = 0x10c0a7
const SOURCE_EXTENSIONS = new Set(['.js', '.mjs', '.cjs', '.ts', '.svelte'])

function seededRandom(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state += 0x6d2b79f5
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4_294_967_296
  }
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function makeEvent(
  scenario: number,
  position: number,
  hour: number,
  id = `event-${scenario}-${position}`,
): CalendarEvent {
  const topic = `Topic ${scenario}.${position}`
  return {
    id,
    title: `${id} · Subject ${scenario}: ${topic}`,
    start: `2026-09-17T${pad(hour)}:00:00`,
    end: `2026-09-17T${pad(hour + 1)}:00:00`,
    subject: `Subject ${scenario}`,
    topic,
    repetition: position + 1,
    completion: position === 0 ? 'planned' : position % 2 ? 'completed' : 'partial',
    recall: position % 2 ? 'well' : null,
    rationale: `Rationale ${id}`,
    is_review: position > 0,
    rescheduled_from_id: null,
  }
}

function generateScenarios(): Scenario[] {
  const random = seededRandom(SEED)
  return Array.from({ length: 8 }, (_, index) => {
    const source: ProviderSource = index % 2 === 0 ? 'ai' : 'fallback'
    const authority: Authority = Math.floor(index / 2) % 2 === 0 ? 'manual' : 'scheduler'
    const eventCount = 2 + Math.floor(random() * 3)
    const initial = Array.from({ length: eventCount }, (_, position) =>
      makeEvent(index, position, 8 + position * 2),
    )
    const changedHour = 15 + Math.floor(random() * 5)
    const authoritative = initial.map((event, position) => {
      if (position !== 0) return { ...event }
      return makeEvent(
        index,
        position,
        changedHour,
        authority === 'scheduler' ? `scheduler-${index}` : event.id,
      )
    })
    return {
      index,
      source,
      authority,
      coachReply: `Move ${initial[0].id} to ${pad(20 + index % 3)}:00 and replace its id with coach-${index}.`,
      initial,
      authoritative,
    }
  })
}

function toSession(event: CalendarEvent): StudySession {
  return {
    id: event.id,
    subject: event.subject,
    topic: event.topic,
    start: event.start,
    end: event.end,
    completion: event.completion,
    recall: event.recall,
    miss_reason: null,
    repetition: event.repetition,
    rationale: event.rationale,
    rescheduled_from_id: event.rescheduled_from_id,
  }
}

function planFor(scenario: Scenario): PlanResponse {
  return {
    plan_id: `plan-${scenario.index}`,
    sessions: scenario.initial.map(toSession),
    summary: 'Generated authority scenario',
    warnings: [],
    unscheduled: [],
  }
}

function minimalHealth(planId: string) {
  return {
    plan_id: planId,
    connection: null,
    summaries: [],
    readiness: {
      occurred_on: '2026-09-17',
      status: 'insufficient_data',
      capacity_percent: 100,
      confidence: 'low',
      factors: [],
      baseline_days: 0,
      sleep_baseline_minutes: null,
      resting_hr_baseline_bpm: null,
      hrv_baseline_rmssd_ms: null,
      disclaimer: 'Test data',
    },
    recommendations: [],
    adjustments: [],
    policy: {
      baseline_days: 14,
      minimum_baseline_days: 3,
      ready_capacity_percent: 100,
      reduce_capacity_percent: 75,
      recovery_capacity_percent: 50,
      retention_days: 30,
    },
  }
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

async function installScenarioRoutes(page: Page, scenario: Scenario) {
  let canonical = scenario.initial.map((event) => ({ ...event }))
  let releaseCoach!: () => void
  const coachMayReturn = new Promise<void>((resolveCoach) => (releaseCoach = resolveCoach))
  const plan = planFor(scenario)

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/plan/latest') return fulfillJson(route, plan)
    if (path === `/api/plan/${plan.plan_id}/events`) return fulfillJson(route, canonical)
    if (path === '/api/privacy') {
      return fulfillJson(route, { anonymous_session: true, api_version: 'test', durable_storage: false, retention_days: 0 })
    }
    if (path === '/api/miss-reasons') return fulfillJson(route, [])
    if (path === '/api/health/dashboard') return fulfillJson(route, minimalHealth(plan.plan_id))
    if (path === '/api/chat') {
      await coachMayReturn
      return fulfillJson(route, {
        reply: { role: 'assistant', content: scenario.coachReply },
        history: [{ role: 'assistant', content: scenario.coachReply }],
        source: scenario.source,
        suggestions: [],
      })
    }
    if (path.includes('/sessions/') && request.method() === 'PUT') {
      canonical = scenario.authoritative.map((event) => ({ ...event }))
      return fulfillJson(route, canonical[0])
    }
    if (path === '/api/progress' && request.method() === 'POST') {
      canonical = scenario.authoritative.map((event) => ({ ...event }))
      return fulfillJson(route, {
        sessions: canonical.map(toSession), changes: [], warnings: [], unscheduled: [],
        insights: null, reschedule: null,
      })
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Unexpected test request"}' })
  })

  return { releaseCoach }
}

function identityAndTimes(events: CalendarEvent[]): RenderedEvent[] {
  return events
    .map(({ id, start, end }) => ({ id, start, end }))
    .sort((left, right) => left.id.localeCompare(right.id))
}

async function renderedIdentityAndTimes(page: Page, expected: CalendarEvent[]): Promise<RenderedEvent[]> {
  const snapshots = await Promise.all(expected.map(async (event) => {
    const rendered = page.getByRole('button', { name: new RegExp(event.id, 'i') })
    await expect(rendered).toHaveCount(1)
    return {
      id: event.id,
      start: await rendered.locator('.event-time').innerText(),
      end: await rendered.getAttribute('aria-label') ?? '',
    }
  }))
  return snapshots.sort((left, right) => left.id.localeCompare(right.id))
}

async function startCoachRequest(page: Page, scenario: Scenario): Promise<void> {
  await page.getByRole('button', { name: 'Mở Study Coach' }).click()
  await page.getByLabel('Bạn muốn hỏi điều gì về kế hoạch?').fill(`Scenario ${scenario.index}`)
  await page.getByRole('button', { name: 'Hỏi Coach' }).click()
  await expect(page.getByRole('button', { name: 'Đang trả lời…' })).toBeDisabled()
}

async function applyAuthoritativeChange(page: Page, scenario: Scenario): Promise<void> {
  const target = page.getByRole('button', { name: new RegExp(scenario.initial[0].id, 'i') })
  await target.click()
  if (scenario.authority === 'manual') {
    await page.getByLabel('Bắt đầu', { exact: true }).fill(scenario.authoritative[0].start.slice(0, 16))
    await page.getByLabel('Kết thúc', { exact: true }).fill(scenario.authoritative[0].end.slice(0, 16))
    await page.getByRole('button', { name: 'Lưu nội dung & thời gian' }).click()
    await expect(target).toHaveAttribute('aria-label', new RegExp(`${pad(new Date(scenario.authoritative[0].start).getHours())}:00`))
  } else {
    await page.getByRole('button', { name: 'Completed', exact: true }).click()
    await page.getByRole('button', { name: 'Xác nhận hoàn thành' }).click()
    await expect(page.getByRole('button', { name: new RegExp(scenario.authoritative[0].id, 'i') })).toBeVisible()
  }
}

async function verifyScenario(browser: Browser, scenario: Scenario): Promise<void> {
  const context = await browser.newContext({ locale: 'en-US', timezoneId: 'UTC' })
  const page = await context.newPage()
  const { releaseCoach } = await installScenarioRoutes(page, scenario)
  await page.goto('/')
  await expect(page.locator('.calendar-app')).toBeVisible()

  const initialDomain = identityAndTimes(scenario.initial)
  const initialRendered = await renderedIdentityAndTimes(page, scenario.initial)
  await startCoachRequest(page, scenario)
  expect(identityAndTimes(scenario.initial)).toEqual(initialDomain)
  expect(await renderedIdentityAndTimes(page, scenario.initial)).toEqual(initialRendered)

  await applyAuthoritativeChange(page, scenario)
  const authoritativeRendered = await renderedIdentityAndTimes(page, scenario.authoritative)
  releaseCoach()
  await expect(page.locator('.coach-response')).toContainText(scenario.coachReply)
  await expect(page.locator('.response-label small')).toHaveText(scenario.source === 'ai' ? 'AI' : 'Dự phòng xác định')

  expect(identityAndTimes(scenario.authoritative)).toEqual(
    identityAndTimes(scenario.authoritative),
  )
  expect(await renderedIdentityAndTimes(page, scenario.authoritative)).toEqual(authoritativeRendered)
  expect(identityAndTimes(scenario.authoritative)).not.toEqual(initialDomain)
  await context.close()
}

function productionFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name)
    if (entry.isDirectory()) return productionFiles(path)
    return SOURCE_EXTENSIONS.has(extname(path)) ? [path] : []
  })
}

test('Property 10: Coach rendering never overrides manual or scheduler authority', async ({ browser }) => {
  // **Validates: Requirements 4.1**
  for (const scenario of generateScenarios()) await verifyScenario(browser, scenario)
})

test('Property 10 source guard: production frontend has no Coach apply or automatic slot search', () => {
  // **Validates: Requirements 4.1**
  const sourceRoot = resolve(process.cwd(), 'src')
  const forbidden = [
    ['Coach-prose apply action', /(?:apply|accept|use)\w*(?:coach|ai)(?:reply|response|suggestion|preview)|(?:coach|ai)(?:reply|response|suggestion|preview)\w*(?:apply|accept|use)/i],
    ['automatic slot-search helper', /(?:find|choose|allocate|compute|suggest)\w*(?:available|open|free|automatic|suggested)\w*(?:slot|time|move)|(?:findSuggestedMove|applyAiPreview|autoSchedule|automaticPlacement|TimeAllocator)/i],
  ] as const
  const findings: string[] = []

  for (const file of productionFiles(sourceRoot)) {
    const source = readFileSync(file, 'utf8')
    for (const [label, pattern] of forbidden) {
      if (pattern.test(source)) findings.push(`${relative(sourceRoot, file)}: ${label}`)
    }
  }
  expect(findings).toEqual([])
})
