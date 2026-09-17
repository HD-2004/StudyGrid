import type {
  Availability,
  BusyBlock,
  PlanRequest,
  Strategy,
  Subject,
} from './types'

export const setupSteps = [
  'basics',
  'materials',
  'topics',
  'availability',
  'commitments',
  'review',
] as const
export type SetupStep = (typeof setupSteps)[number]

export const weekdayKeys = ['0', '1', '2', '3', '4', '5', '6'] as const
export type WeekdayKey = (typeof weekdayKeys)[number]
export type DailyHours = Record<WeekdayKey, number>

export interface MaterialAnalysisState {
  text: string
  url: string
  file: File | null
  busy: boolean
  source: 'ai' | 'fallback' | null
  truncated: boolean
  message: string | null
  error: string | null
}

export type PlanDraftSubject = Subject

export interface PlanDraftAvailability
  extends Omit<Availability, 'weekday_minutes' | 'break_minutes'> {
  weekday_hours: DailyHours
}

export interface PlanDraft {
  subjects: PlanDraftSubject[]
  materials: MaterialAnalysisState[]
  availability: PlanDraftAvailability
  start_date?: string
  strategy: Strategy
  notes?: string
}
export type ValidationIssueCode =
  | 'required'
  | 'invalid-date'
  | 'out-of-range'
  | 'invalid-time-range'
  | 'short-day'

export interface ValidationIssue {
  fieldId: string
  code: ValidationIssueCode
  severity: 'error' | 'warning'
}

export interface StepValidation {
  valid: boolean
  issues: ValidationIssue[]
  firstInvalidFieldId?: string
}

export interface AvailabilityTotals {
  weekdayMinutes: Record<WeekdayKey, number>
  weeklyMinutes: number
  weeklyHours: number
  activeStudyDays: number
  usableFullSessionMinutes: number
  fullSessionCount: number
  shortDayKeys: WeekdayKey[]
  shortBreakMinutes: number
}

function isDate(value: string | undefined): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return (
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
  )
}

function issue(
  issues: ValidationIssue[],
  fieldId: string,
  code: ValidationIssueCode,
  severity: ValidationIssue['severity'] = 'error',
): void {
  issues.push({ fieldId, code, severity })
}

function integerInRange(value: number, minimum: number, maximum: number): boolean {
  return Number.isInteger(value) && value >= minimum && value <= maximum
}

export function hoursToMinutes(hours: number): number {
  if (!Number.isFinite(hours)) return 0
  return Math.max(0, Math.round(hours * 60))
}

export function deriveAvailabilityTotals(
  dailyHours: Readonly<DailyHours>,
  sessionLengthMinutes: number,
): AvailabilityTotals {
  const weekdayMinutes = {} as Record<WeekdayKey, number>
  const shortDayKeys: WeekdayKey[] = []
  let weeklyMinutes = 0
  let activeStudyDays = 0
  let usableFullSessionMinutes = 0
  let fullSessionCount = 0

  for (const key of weekdayKeys) {
    const minutes = hoursToMinutes(dailyHours[key])
    weekdayMinutes[key] = minutes
    weeklyMinutes += minutes
    if (minutes > 0) activeStudyDays += 1
    if (minutes > 0 && minutes < sessionLengthMinutes) {
      shortDayKeys.push(key)
    } else if (minutes >= sessionLengthMinutes && sessionLengthMinutes > 0) {
      const sessions = Math.floor(minutes / sessionLengthMinutes)
      fullSessionCount += sessions
      usableFullSessionMinutes += sessions * sessionLengthMinutes
    }
  }

  return {
    weekdayMinutes,
    weeklyMinutes,
    weeklyHours: weeklyMinutes / 60,
    activeStudyDays,
    usableFullSessionMinutes,
    fullSessionCount,
    shortDayKeys,
    shortBreakMinutes: Math.ceil(sessionLengthMinutes * 0.1),
  }
}
function validateBasics(draft: Readonly<PlanDraft>, issues: ValidationIssue[]): void {
  if (!isDate(draft.start_date)) issue(issues, 'plan-start', 'invalid-date')
  const { earliest, latest } = draft.availability
  if (!earliest) issue(issues, 'earliest-time', 'required')
  if (!latest) issue(issues, 'latest-time', 'required')
  if (earliest && latest && earliest >= latest) {
    issue(issues, 'latest-time', 'invalid-time-range')
  }
}

function validateSubjects(draft: Readonly<PlanDraft>, issues: ValidationIssue[]): void {
  if (draft.subjects.length === 0) issue(issues, 'subjects', 'required')
  draft.subjects.forEach((subject, subjectIndex) => {
    if (!subject.name.trim()) issue(issues, `subject-${subjectIndex}`, 'required')
    if (!isDate(subject.exam_date)) issue(issues, `exam-${subjectIndex}`, 'invalid-date')
    if (!integerInRange(subject.priority, 1, 5)) {
      issue(issues, `prio-${subjectIndex}`, 'out-of-range')
    }
    const nonblankTopics = subject.topics.filter((topic) => topic.name.trim())
    if (nonblankTopics.length === 0) issue(issues, `topic-${subjectIndex}-0`, 'required')
    subject.topics.forEach((topic, topicIndex) => {
      if (topic.name.trim() && !integerInRange(topic.estimated_minutes, 15, 600)) {
        issue(issues, `topic-minutes-${subjectIndex}-${topicIndex}`, 'out-of-range')
      }
    })
  })
}

function validateAvailability(draft: Readonly<PlanDraft>, issues: ValidationIssue[]): void {
  const length = draft.availability.session_length_minutes
  if (!integerInRange(length, 15, 240)) issue(issues, 'session-length', 'out-of-range')
  if (!integerInRange(draft.availability.long_break_minutes, 30, 180)) {
    issue(issues, 'long-break', 'out-of-range')
  }
  const totals = deriveAvailabilityTotals(draft.availability.weekday_hours, length)
  weekdayKeys.forEach((key) => {
    const hours = draft.availability.weekday_hours[key]
    if (!Number.isFinite(hours) || hours < 0 || hours > 12) {
      issue(issues, `day-${key}`, 'out-of-range')
    }
  })
  totals.shortDayKeys.forEach((key) => issue(issues, `day-${key}`, 'short-day', 'warning'))
}

function validateCommitments(draft: Readonly<PlanDraft>, issues: ValidationIssue[]): void {
  draft.availability.busy.forEach((block, index) => {
    if (!integerInRange(block.weekday, 0, 6)) {
      issue(issues, `busy-day-${index}`, 'out-of-range')
    }
    if (!block.start) issue(issues, `busy-start-${index}`, 'required')
    if (!block.end) issue(issues, `busy-end-${index}`, 'required')
    if (block.start && block.end && block.start >= block.end) {
      issue(issues, `busy-end-${index}`, 'invalid-time-range')
    }
  })
}

export function validateSetupStep(
  step: SetupStep,
  draft: Readonly<PlanDraft>,
): StepValidation {
  const issues: ValidationIssue[] = []
  if (step === 'basics') validateBasics(draft, issues)
  if (step === 'materials' || step === 'topics') validateSubjects(draft, issues)
  if (step === 'availability') validateAvailability(draft, issues)
  if (step === 'commitments') validateCommitments(draft, issues)
  if (step === 'review') {
    validateBasics(draft, issues)
    validateSubjects(draft, issues)
    validateAvailability(draft, issues)
    validateCommitments(draft, issues)
  }
  const firstError = issues.find(({ severity }) => severity === 'error')
  return {
    valid: !firstError,
    issues,
    ...(firstError ? { firstInvalidFieldId: firstError.fieldId } : {}),
  }
}

function cleanSubject(subject: Readonly<PlanDraftSubject>): Subject {
  return {
    name: subject.name.trim(),
    exam_date: subject.exam_date,
    priority: subject.priority,
    topics: subject.topics
      .filter((topic) => topic.name.trim())
      .map((topic) => ({
        ...topic,
        name: topic.name.trim(),
        depends_on: topic.depends_on?.map((dependency) => dependency.trim()).filter(Boolean),
      })),
  }
}

function cleanBusyBlock(block: Readonly<BusyBlock>): BusyBlock {
  return { ...block, label: block.label.trim() }
}

export function toPlanRequest(draft: Readonly<PlanDraft>): PlanRequest {
  const validation = validateSetupStep('review', draft)
  if (!validation.valid) {
    throw new TypeError(`Cannot convert invalid plan draft: ${validation.firstInvalidFieldId}`)
  }
  const totals = deriveAvailabilityTotals(
    draft.availability.weekday_hours,
    draft.availability.session_length_minutes,
  )
  return {
    subjects: draft.subjects.filter((subject) => subject.name.trim()).map(cleanSubject),
    availability: {
      weekday_minutes: totals.weekdayMinutes,
      earliest: draft.availability.earliest,
      latest: draft.availability.latest,
      session_length_minutes: draft.availability.session_length_minutes,
      break_minutes: totals.shortBreakMinutes,
      long_break_minutes: draft.availability.long_break_minutes,
      busy: draft.availability.busy.map(cleanBusyBlock),
    },
    start_date: draft.start_date,
    strategy: draft.strategy,
    notes: draft.notes?.trim(),
  }
}
