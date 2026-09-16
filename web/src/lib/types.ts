// Mirrors the backend contract in ARCHITECTURE.md. Keep in sync with
// app/api/schemas.py and app/models.py.

export type Difficulty = 'easy' | 'medium' | 'hard'
export type Completion = 'planned' | 'completed' | 'partial' | 'not_completed'
export type Recall = 'well' | 'medium' | 'poor'
export type Strategy = 'fresh' | 'remaining' | 'exam_rush'
export type ChangeType = 'moved' | 'added' | 'blocked'
export type MissReason =
  | 'club'
  | 'exercise'
  | 'social'
  | 'rest'
  | 'mood'
  | 'emergency'
  | 'other'

export interface ReasonOption {
  value: MissReason
  label: string
}

export interface ReasonCount {
  reason: MissReason
  label: string
  count: number
  minutes_lost: number
}

/** Time-use aggregation (HACKATHON.md 8.3). */
export interface Insights {
  sessions_logged: number
  completed: number
  missed: number
  partial: number
  minutes_studied: number
  minutes_lost: number
  reasons: ReasonCount[]
  weak_weekdays: number[]
  recall_mix: Record<string, number>
  observations: string[]
  confident: boolean
}

export interface Topic {
  name: string
  difficulty: Difficulty
  estimated_minutes: number
  already_studied?: boolean
  depends_on?: string[]
}

export interface Subject {
  name: string
  exam_date: string // YYYY-MM-DD
  topics: Topic[]
  priority: number
}

export interface BusyBlock {
  weekday: number // 0 = Monday
  start: string // HH:MM:SS
  end: string
  label: string
}

export interface Availability {
  weekday_minutes: Record<string, number>
  earliest?: string
  latest?: string
  session_length_minutes: number
  break_minutes?: number
  busy: BusyBlock[]
}

export interface PlanRequest {
  subjects: Subject[]
  availability: Availability
  start_date?: string
  strategy: Strategy
  notes?: string
}

export interface StudySession {
  id: string
  subject: string
  topic: string
  start: string
  end: string
  completion: Completion
  recall: Recall | null
  miss_reason: MissReason | null
  repetition: number
  rationale: string
}

export interface PlanResponse {
  plan_id: string
  sessions: StudySession[]
  summary: string
  warnings: string[]
  unscheduled: string[]
}

/** Calendar-shaped session. Times are ISO 8601 local, no offset. */
export interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
  subject: string
  topic: string
  repetition: number
  completion: Completion
  recall: Recall | null
  rationale: string
  is_review: boolean
}

export interface PlanChange {
  type: ChangeType
  topic: string
  why: string
  session_id: string | null
  moved_from: string | null
  moved_to: string | null
}

export interface ProgressResponse {
  sessions: StudySession[]
  changes: PlanChange[]
  warnings: string[]
  insights: Insights | null
}

export interface AnalyzeResponse {
  topics: Topic[]
  source: 'ai' | 'fallback'
}
