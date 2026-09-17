import { expect, test } from '@playwright/test'
import {
  deriveAvailabilityTotals,
  toPlanRequest,
  validateSetupStep,
  type PlanDraft,
} from '../src/lib/setup-state'
import {
  deriveScheduleViewModel,
  projectEvents,
  visibleSubjectsFor,
} from '../src/lib/schedule-state'
import type { CalendarEvent } from '../src/lib/types'

function validDraft(): PlanDraft {
  return {
    strategy: 'fresh',
    start_date: '2026-04-01',
    notes: '  Focus on proofs  ',
    subjects: [{
      name: '  Linear Algebra  ',
      exam_date: '2026-05-01',
      priority: 3,
      topics: [
        { name: '  Vector spaces  ', difficulty: 'medium', estimated_minutes: 60 },
        { name: '   ', difficulty: 'easy', estimated_minutes: 30 },
      ],
    }],
    materials: [{
      text: 'syllabus',
      url: '',
      file: null,
      busy: false,
      source: 'fallback',
      truncated: false,
      message: 'one topic',
      error: null,
    }],
    availability: {
      weekday_hours: { '0': 1, '1': 0.5, '2': 1.25, '3': 0, '4': 0, '5': 0, '6': 0 },
      earliest: '09:00',
      latest: '22:00',
      session_length_minutes: 60,
      long_break_minutes: 45,
      busy: [{ weekday: 0, start: '12:00', end: '13:00', label: ' Lunch ' }],
    },
  }
}

function event(id: string, subject: string, start: string): CalendarEvent {
  return {
    id,
    title: `${subject}: topic`,
    start,
    end: start.replace(':00:00', ':30:00'),
    subject,
    topic: 'topic',
    repetition: 1,
    completion: 'planned',
    recall: null,
    rationale: '',
    is_review: false,
    rescheduled_from_id: null,
  }
}
test('converts a valid draft to the existing request wire shape and derives capacity', () => {
  const draft = validDraft()
  const totals = deriveAvailabilityTotals(draft.availability.weekday_hours, 60)

  expect(totals.weekdayMinutes).toEqual({
    '0': 60, '1': 30, '2': 75, '3': 0, '4': 0, '5': 0, '6': 0,
  })
  expect(totals.weeklyMinutes).toBe(165)
  expect(totals.weeklyHours).toBe(2.75)
  expect(totals.shortDayKeys).toEqual(['1'])
  expect(totals.usableFullSessionMinutes).toBe(120)
  expect(totals.fullSessionCount).toBe(2)
  expect(totals.shortBreakMinutes).toBe(6)

  const request = toPlanRequest(draft)
  expect(request.availability.weekday_minutes).toEqual(totals.weekdayMinutes)
  expect(request.subjects[0].name).toBe('Linear Algebra')
  expect(request.subjects[0].topics.map(({ name }) => name)).toEqual(['Vector spaces'])
  expect(request.availability.busy[0].label).toBe('Lunch')
  expect(request.notes).toBe('Focus on proofs')
  expect('weeklyMinutes' in request.availability).toBe(false)
})

test('validates setup without mutation and reports short days as warnings', () => {
  const draft = validDraft()
  const before = JSON.stringify(draft)
  const validation = validateSetupStep('review', draft)

  expect(validation.valid).toBe(true)
  expect(validation.issues).toContainEqual({
    fieldId: 'day-1', code: 'short-day', severity: 'warning',
  })
  expect(JSON.stringify(draft)).toBe(before)

  draft.availability.latest = '08:00'
  const invalid = validateSetupStep('review', draft)
  expect(invalid.valid).toBe(false)
  expect(invalid.firstInvalidFieldId).toBe('latest-time')
  expect(() => toPlanRequest(draft)).toThrow(/latest-time/)
})

test('projects visible events once in deterministic local-start then ID order', () => {
  const canonical = [
    event('b', 'Math', '2026-04-01T10:00:00Z'),
    event('hidden', 'Biology', '2026-04-01T08:00:00Z'),
    event('a', 'Math', '2026-04-01T10:00:00Z'),
    event('c', 'Math', '2026-04-01T09:00:00Z'),
  ]
  const before = JSON.stringify(canonical)
  const visible = new Set(['Math'])
  const projected = projectEvents(canonical, visible, 'en', 'UTC')
  const reversed = projectEvents([...canonical].reverse(), visible, 'en', 'UTC')

  expect([...projected.values()].flat().map(({ event: item }) => item.id)).toEqual(['c', 'a', 'b'])
  expect([...reversed.values()].flat().map(({ event: item }) => item.id)).toEqual(['c', 'a', 'b'])
  expect(JSON.stringify(canonical)).toBe(before)
})
test('derives equal view models and reversible filters from equal inputs', () => {
  const canonical = [
    event('2', 'Math', '2026-04-02T10:00:00Z'),
    event('1', 'Biology', '2026-04-01T10:00:00Z'),
  ]
  const all = visibleSubjectsFor(canonical, [])
  const hiddenMath = visibleSubjectsFor(canonical, ['Math'])
  const restored = visibleSubjectsFor(canonical, ['Math', 'Math'].filter((_, index) => index === 1))
  expect([...hiddenMath]).toEqual(['Biology'])
  expect([...restored]).toEqual(['Biology'])

  const input = {
    events: canonical,
    visibleSubjects: all,
    locale: 'en' as const,
    timezone: 'UTC',
    anchorDate: '2026-04-01',
    view: 'agenda' as const,
    unscheduled: ['one item'],
  }
  const first = deriveScheduleViewModel(input)
  const second = deriveScheduleViewModel(input)
  expect({ ...first, eventsByDate: [...first.eventsByDate] }).toEqual({
    ...second,
    eventsByDate: [...second.eventsByDate],
  })
  expect(first.events.map(({ event: item }) => item.id)).toEqual(['1', '2'])
  expect(JSON.stringify(canonical)).toBe(JSON.stringify(input.events))
})
