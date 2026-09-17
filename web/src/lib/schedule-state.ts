import type { Locale } from './i18n/keys'
import type {
  CalendarEvent,
  HealthDashboard,
  PlanChange,
  ReadinessAssessment,
} from './types'

export type ScheduleView = 'week' | 'month' | 'agenda'

export interface AdaptationViewModel {
  changes: readonly PlanChange[]
  warnings: readonly string[]
  unscheduled: readonly string[]
}

export interface ScheduleItem {
  event: CalendarEvent
  localDate: string
  localStart: string
  localEnd: string
}

export interface ScheduleViewModel {
  anchorDate: string
  timezone: string
  locale: Locale
  view: ScheduleView
  events: readonly ScheduleItem[]
  eventsByDate: ReadonlyMap<string, readonly ScheduleItem[]>
  visibleSubjects: ReadonlySet<string>
  unscheduled: readonly string[]
  readiness: ReadinessAssessment | null
  latestAdaptation: AdaptationViewModel | null
}

export interface ScheduleProjectionInput {
  events: readonly CalendarEvent[]
  visibleSubjects: ReadonlySet<string>
  locale: Locale
  timezone: string
  anchorDate: string
  view: ScheduleView
  unscheduled?: readonly string[]
  readiness?: ReadinessAssessment | null
  latestAdaptation?: AdaptationViewModel | null
}

const dateParts = new Map<string, Intl.DateTimeFormat>()
const timeParts = new Map<string, Intl.DateTimeFormat>()

function formatter(
  cache: Map<string, Intl.DateTimeFormat>,
  locale: Locale,
  timezone: string,
  options: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormat {
  const key = `${locale}|${timezone}`
  let value = cache.get(key)
  if (!value) {
    value = new Intl.DateTimeFormat(locale, { ...options, timeZone: timezone })
    cache.set(key, value)
  }
  return value
}

function parseEventTime(value: string): Date {
  const instant = new Date(value)
  if (Number.isNaN(instant.getTime())) throw new RangeError(`Invalid event time: ${value}`)
  return instant
}

function partsRecord(parts: Intl.DateTimeFormatPart[]): Record<string, string> {
  return Object.fromEntries(parts.map(({ type, value }) => [type, value]))
}

function localDateAndTime(
  value: string,
  locale: Locale,
  timezone: string,
): { date: string; time: string } {
  const instant = parseEventTime(value)
  const date = partsRecord(
    formatter(dateParts, locale, timezone, {
      calendar: 'iso8601',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(instant),
  )
  const time = partsRecord(
    formatter(timeParts, locale, timezone, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(instant),
  )
  return {
    date: `${date.year}-${date.month}-${date.day}`,
    time: `${time.hour}:${time.minute}:${time.second}`,
  }
}
function compareScheduleItems(left: ScheduleItem, right: ScheduleItem): number {
  return left.localStart.localeCompare(right.localStart) || left.event.id.localeCompare(right.event.id)
}

export function projectEvents(
  events: readonly CalendarEvent[],
  visibleSubjects: ReadonlySet<string>,
  locale: Locale,
  timezone: string,
): ReadonlyMap<string, readonly ScheduleItem[]> {
  const buckets = new Map<string, ScheduleItem[]>()
  for (const event of events) {
    if (!visibleSubjects.has(event.subject)) continue
    const start = localDateAndTime(event.start, locale, timezone)
    const end = localDateAndTime(event.end, locale, timezone)
    const item: ScheduleItem = {
      event: { ...event },
      localDate: start.date,
      localStart: start.time,
      localEnd: end.time,
    }
    const bucket = buckets.get(start.date)
    if (bucket) bucket.push(item)
    else buckets.set(start.date, [item])
  }

  return new Map(
    [...buckets.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([date, items]) => [date, items.sort(compareScheduleItems)]),
  )
}

export function deriveScheduleViewModel(input: ScheduleProjectionInput): ScheduleViewModel {
  const visibleSubjects = new Set(input.visibleSubjects)
  const eventsByDate = projectEvents(input.events, visibleSubjects, input.locale, input.timezone)
  const events = [...eventsByDate.values()].flat()
  return {
    anchorDate: input.anchorDate,
    timezone: input.timezone,
    locale: input.locale,
    view: input.view,
    events,
    eventsByDate,
    visibleSubjects,
    unscheduled: [...(input.unscheduled ?? [])],
    readiness: input.readiness ?? null,
    latestAdaptation: input.latestAdaptation
      ? {
          changes: input.latestAdaptation.changes.map((change) => ({ ...change })),
          warnings: [...input.latestAdaptation.warnings],
          unscheduled: [...input.latestAdaptation.unscheduled],
        }
      : null,
  }
}

export function visibleSubjectsFor(
  events: readonly CalendarEvent[],
  hiddenSubjects: readonly string[],
): ReadonlySet<string> {
  const hidden = new Set(hiddenSubjects)
  return new Set(events.map(({ subject }) => subject).filter((subject) => !hidden.has(subject)))
}

export function readinessFromHealth(health: HealthDashboard | null): ReadinessAssessment | null {
  return health?.readiness ?? null
}
