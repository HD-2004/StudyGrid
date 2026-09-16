export type Difficulty = 'easy' | 'medium' | 'hard'
export type Completion = 'planned' | 'completed' | 'partial' | 'not_completed'
export type Recall = 'well' | 'medium' | 'poor'
export type Strategy = 'fresh' | 'remaining' | 'exam_rush'
export type AnalysisSource = 'ai' | 'fallback'

export interface Topic {
  name: string
  difficulty: Difficulty
  estimated_minutes: number
  already_studied: boolean
  depends_on: string[]
}

export interface Subject {
  name: string
  exam_date: string
  topics: Topic[]
  priority: number
}

export interface BusyBlock {
  weekday: number
  start: string
  end: string
  label: string
}

export interface Availability {
  weekday_minutes: Record<number, number>
  earliest: string
  latest: string
  session_length_minutes: number
  break_minutes: number
  busy: BusyBlock[]
}

export interface PlanRequest {
  subjects: Subject[]
  availability: Availability
  start_date: string
  strategy: Strategy
  notes: string
}

export interface StudySession {
  id: string
  subject: string
  topic: string
  start: string
  end: string
  completion: Completion
  recall: Recall | null
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

export type ChangeType = 'moved' | 'added' | 'blocked'

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
}

export interface AnalyzeResponse {
  topics: Topic[]
  source: AnalysisSource
}

export interface DraftSubject extends Subject {
  materialText: string
  analysisSource: AnalysisSource | null
}
