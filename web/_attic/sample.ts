import type { Availability, DraftSubject, Strategy } from './types'

function formatDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function dateFromToday(days: number): string {
  const result = new Date()
  result.setHours(12, 0, 0, 0)
  result.setDate(result.getDate() + days)
  return formatDate(result)
}

export function today(): string {
  return dateFromToday(0)
}

export const defaultAvailability: Availability = {
  weekday_minutes: {
    0: 120,
    1: 90,
    2: 120,
    3: 90,
    4: 120,
    5: 180,
    6: 60,
  },
  earliest: '09:00',
  latest: '21:00',
  session_length_minutes: 50,
  break_minutes: 10,
  busy: [
    { weekday: 0, start: '09:00', end: '11:00', label: 'Lecture' },
    { weekday: 3, start: '14:00', end: '16:00', label: 'Lab' },
  ],
}

const biologyMaterial = `Cell structure and organelles
Cell division and the cell cycle
Mendelian inheritance
Advanced gene regulation
Population genetics`

const algebraMaterial = `Vectors and vector spaces
Linear transformations
Matrix operations
Eigenvalues and eigenvectors
Orthogonality and least squares`

export function createSample(strategy: Strategy = 'fresh'): DraftSubject[] {
  if (strategy === 'exam_rush') {
    return [
      {
        name: 'Organic Chemistry',
        exam_date: dateFromToday(5),
        priority: 5,
        materialText: 'Reaction mechanisms\nStereochemistry\nSpectroscopy\nCarbonyl chemistry',
        analysisSource: null,
        topics: [
          {
            name: 'Reaction mechanisms',
            difficulty: 'hard',
            estimated_minutes: 120,
            already_studied: false,
            depends_on: [],
          },
          {
            name: 'Stereochemistry',
            difficulty: 'hard',
            estimated_minutes: 90,
            already_studied: false,
            depends_on: [],
          },
          {
            name: 'Spectroscopy',
            difficulty: 'medium',
            estimated_minutes: 75,
            already_studied: false,
            depends_on: [],
          },
          {
            name: 'Carbonyl chemistry',
            difficulty: 'hard',
            estimated_minutes: 120,
            already_studied: false,
            depends_on: ['Reaction mechanisms'],
          },
        ],
      },
    ]
  }

  const alreadyStudied = strategy === 'remaining'
  return [
    {
      name: 'Biology',
      exam_date: dateFromToday(strategy === 'remaining' ? 15 : 24),
      priority: 4,
      materialText: biologyMaterial,
      analysisSource: null,
      topics: [
        {
          name: 'Cell structure and organelles',
          difficulty: 'easy',
          estimated_minutes: 45,
          already_studied: alreadyStudied,
          depends_on: [],
        },
        {
          name: 'Cell division and the cell cycle',
          difficulty: 'medium',
          estimated_minutes: 60,
          already_studied: false,
          depends_on: ['Cell structure and organelles'],
        },
        {
          name: 'Advanced gene regulation',
          difficulty: 'hard',
          estimated_minutes: 90,
          already_studied: false,
          depends_on: [],
        },
      ],
    },
    {
      name: 'Linear Algebra',
      exam_date: dateFromToday(strategy === 'remaining' ? 20 : 31),
      priority: 5,
      materialText: algebraMaterial,
      analysisSource: null,
      topics: [
        {
          name: 'Vectors and vector spaces',
          difficulty: 'easy',
          estimated_minutes: 50,
          already_studied: alreadyStudied,
          depends_on: [],
        },
        {
          name: 'Eigenvalues and eigenvectors',
          difficulty: 'hard',
          estimated_minutes: 120,
          already_studied: false,
          depends_on: ['Vectors and vector spaces'],
        },
        {
          name: 'Orthogonality and least squares',
          difficulty: 'medium',
          estimated_minutes: 75,
          already_studied: false,
          depends_on: ['Vectors and vector spaces'],
        },
      ],
    },
  ]
}

export function blankSubject(): DraftSubject {
  return {
    name: '',
    exam_date: dateFromToday(21),
    priority: 3,
    materialText: '',
    analysisSource: null,
    topics: [],
  }
}
