// Demo seed data for the three entry points in HACKATHON.md section 7.
// One click loads a realistic plan, which matters when demoing on a clock.

import type { PlanRequest, Strategy } from './types'

function isoDaysFromNow(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const WEEKDAY_MINUTES = { '0': 120, '1': 120, '2': 60, '3': 120, '4': 60, '5': 180, '6': 0 }

const FIXED_COMMITMENTS = [
  { weekday: 0, start: '09:00:00', end: '11:00:00', label: 'Lecture' },
  { weekday: 2, start: '13:00:00', end: '15:00:00', label: 'Lab' },
]

export const SEEDS: Record<Strategy, { label: string; hint: string; request: PlanRequest }> = {
  fresh: {
    label: 'New semester',
    hint: 'Nothing studied yet, exams three weeks out.',
    request: {
      strategy: 'fresh',
      start_date: isoDaysFromNow(0),
      subjects: [
        {
          name: 'Linear Algebra',
          exam_date: isoDaysFromNow(21),
          priority: 5,
          topics: [
            { name: 'Vectors and spans', difficulty: 'easy', estimated_minutes: 60 },
            {
              name: 'Eigenvalues',
              difficulty: 'hard',
              estimated_minutes: 150,
              depends_on: ['Vectors and spans'],
            },
            { name: 'Determinants', difficulty: 'medium', estimated_minutes: 90 },
          ],
        },
        {
          name: 'Cell Biology',
          exam_date: isoDaysFromNow(14),
          priority: 3,
          topics: [
            { name: 'Mitosis', difficulty: 'medium', estimated_minutes: 60 },
            { name: 'Membrane transport', difficulty: 'hard', estimated_minutes: 100 },
          ],
        },
      ],
      availability: {
        weekday_minutes: WEEKDAY_MINUTES,
        session_length_minutes: 50,
        busy: FIXED_COMMITMENTS,
      },
    },
  },

  remaining: {
    label: 'Mid-semester',
    hint: 'Some material already covered; it needs review, not a first pass.',
    request: {
      strategy: 'remaining',
      start_date: isoDaysFromNow(0),
      subjects: [
        {
          name: 'Organic Chemistry',
          exam_date: isoDaysFromNow(18),
          priority: 4,
          topics: [
            { name: 'Alkanes', difficulty: 'easy', estimated_minutes: 50, already_studied: true },
            {
              name: 'Stereochemistry',
              difficulty: 'medium',
              estimated_minutes: 80,
              already_studied: true,
            },
            { name: 'Reaction mechanisms', difficulty: 'hard', estimated_minutes: 180 },
          ],
        },
      ],
      availability: {
        weekday_minutes: WEEKDAY_MINUTES,
        session_length_minutes: 50,
        busy: FIXED_COMMITMENTS,
      },
    },
  },

  exam_rush: {
    label: 'Exam in three days',
    hint: 'Not enough time for everything. Coverage beats depth.',
    request: {
      strategy: 'exam_rush',
      start_date: isoDaysFromNow(0),
      subjects: [
        {
          name: 'Macroeconomics',
          exam_date: isoDaysFromNow(3),
          priority: 5,
          topics: [
            { name: 'GDP accounting', difficulty: 'medium', estimated_minutes: 90 },
            { name: 'Monetary policy', difficulty: 'hard', estimated_minutes: 120 },
            { name: 'Fiscal multipliers', difficulty: 'hard', estimated_minutes: 120 },
            { name: 'Exchange rates', difficulty: 'hard', estimated_minutes: 120 },
            { name: 'Inflation models', difficulty: 'medium', estimated_minutes: 90 },
          ],
        },
      ],
      availability: {
        weekday_minutes: WEEKDAY_MINUTES,
        session_length_minutes: 50,
        busy: FIXED_COMMITMENTS,
      },
    },
  },
}
