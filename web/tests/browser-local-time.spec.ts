import { expect, test } from '@playwright/test'
import { readFileSync, readdirSync } from 'node:fs'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createI18n, supportedLocales, type Locale } from '../src/lib/i18n'
import { deriveScheduleViewModel, type ScheduleView } from '../src/lib/schedule-state'
import type { CalendarEvent } from '../src/lib/types'

type TimezoneCase = {
  timezone: string
  dstPairs: readonly (readonly [string, string])[]
}

const TIMEZONE_CASES: readonly TimezoneCase[] = [
  {
    timezone: 'America/New_York',
    dstPairs: [
      ['2026-03-08T06:59:00.000Z', '2026-03-08T07:00:00.000Z'],
      ['2026-11-01T05:59:00.000Z', '2026-11-01T06:00:00.000Z'],
    ],
  },
  {
    timezone: 'Europe/London',
    dstPairs: [
      ['2026-03-29T00:59:00.000Z', '2026-03-29T01:00:00.000Z'],
      ['2026-10-25T00:59:00.000Z', '2026-10-25T01:00:00.000Z'],
    ],
  },
  { timezone: 'Asia/Ho_Chi_Minh', dstPairs: [] },
  { timezone: 'UTC', dstPairs: [] },
]

function deterministicInstants(seed = 0x4b1d5eed, count = 24): string[] {
  let state = seed >>> 0
  const first = Date.parse('2024-01-01T00:00:00.000Z')
  const span = Date.parse('2029-01-01T00:00:00.000Z') - first
  return Array.from({ length: count }, () => {
    state ^= state << 13
    state ^= state >>> 17
    state ^= state << 5
    const epoch = first + Math.floor(((state >>> 0) / 0x1_0000_0000) * span)
    return new Date(Math.floor(epoch / 60_000) * 60_000).toISOString()
  })
}

function productionFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? productionFiles(path) : ['.ts', '.svelte'].includes(extname(path)) ? [path] : []
  })
}

const GENERATED_CASES = 24
const VIEWS: readonly ScheduleView[] = ['week', 'month', 'agenda']

function supportsTimezone(timezone: string): boolean {
  try {
    new Intl.DateTimeFormat('en', { timeZone: timezone }).format(0)
    return true
  } catch {
    return false
  }
}

function expectedLocalParts(instant: string, locale: Locale, timezone: string) {
  const date = Object.fromEntries(new Intl.DateTimeFormat(locale, {
    calendar: 'iso8601', year: 'numeric', month: '2-digit', day: '2-digit', timeZone: timezone,
  }).formatToParts(new Date(instant)).map(({ type, value }) => [type, value]))
  const time = Object.fromEntries(new Intl.DateTimeFormat(locale, {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZone: timezone,
  }).formatToParts(new Date(instant)).map(({ type, value }) => [type, value]))
  return {
    date: `${date.year}-${date.month}-${date.day}`,
    time: `${time.hour}:${time.minute}:${time.second}`,
  }
}

function eventFor(instant: string, index: number): CalendarEvent {
  return {
    id: `property-event-${index}`,
    title: `Boundary session ${index}`,
    subject: 'Temporal systems',
    topic: 'Browser-local formatting',
    start: instant,
    end: new Date(Date.parse(instant) + 45 * 60_000).toISOString(),
    repetition: index % 4,
    completion: index % 2 === 0 ? 'planned' : 'completed',
    recall: null,
    rationale: 'Generated browser-local consistency case',
    is_review: index % 3 === 0,
    rescheduled_from_id: null,
  }
}

test('Property 4: Browser-local time consistency', () => {
  // **Validates: Requirements 1.4**
  const generated = deterministicInstants(0x4b1d5eed, GENERATED_CASES)

  for (const { timezone, dstPairs } of TIMEZONE_CASES.filter(({ timezone }) => supportsTimezone(timezone))) {
    const instants = [...generated, ...dstPairs.flat()]
    for (const locale of supportedLocales) {
      const formatter = createI18n(locale)
      for (const [index, instant] of instants.entries()) {
        const event = eventFor(instant, index)
        const expectedStart = expectedLocalParts(event.start, locale, timezone)
        const expectedEnd = expectedLocalParts(event.end, locale, timezone)
        const localTimeOptions = {
          hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZone: timezone,
        } as const
        const visibleStart = formatter.time(event.start, localTimeOptions)
        const visibleEnd = formatter.time(event.end, localTimeOptions)
        const statusLabel = formatter.enumLabel('completion', event.completion)
        const sessionKindLabel = event.is_review
          ? formatter.t('session.reviewNumber', { repetition: event.repetition })
          : formatter.t('session.firstPass')
        const accessibleLabel = formatter.t('calendar.eventLabel', {
          title: event.title,
          subject: event.subject,
          start: visibleStart,
          end: visibleEnd,
          status: statusLabel,
          review: sessionKindLabel,
        })

        for (const view of VIEWS) {
          const model = deriveScheduleViewModel({
            events: [event],
            visibleSubjects: new Set([event.subject]),
            locale,
            timezone,
            anchorDate: expectedStart.date,
            view,
          })
          const item = model.events[0]
          const context = `${timezone}/${locale}/${view}/${instant}`

          expect(item.localDate, context).toBe(expectedStart.date)
          expect(item.localStart, context).toBe(expectedStart.time)
          expect(item.localEnd, context).toBe(expectedEnd.time)
          expect(visibleStart, context).toBe(expectedStart.time)
          expect(visibleEnd, context).toBe(expectedEnd.time)
          expect(accessibleLabel, context).toContain(visibleStart)
          expect(accessibleLabel, context).toContain(visibleEnd)
          expect(accessibleLabel, context).toContain(statusLabel)
          expect(accessibleLabel, context).toContain(sessionKindLabel)
          expect(accessibleLabel, context).not.toMatch(/GMT\s*\+\s*0?7/i)
        }
      }
    }
  }
})

test('Property 4 source guard: production schedule presentation has no hard-coded GMT+07', () => {
  // **Validates: Requirements 1.4**
  const sourceRoot = fileURLToPath(new URL('../src', import.meta.url))
  const offenders = productionFiles(sourceRoot).flatMap((path) => {
    const matches = [...readFileSync(path, 'utf8').matchAll(/GMT\s*\+\s*0?7/gi)]
    return matches.map((match) => `${path.slice(sourceRoot.length + 1)}:${match.index}:${match[0]}`)
  })

  expect(offenders, 'timezone labels must use the resolved browser-local contract').toEqual([])
})