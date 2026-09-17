// Mirrors the backend contract in ARCHITECTURE.md. Keep in sync with
// app/api/schemas.py and app/models.py.

export type Difficulty = 'easy' | 'medium' | 'hard'
export type Completion = 'planned' | 'completed' | 'partial' | 'not_completed'
export type Recall = 'well' | 'medium' | 'poor'
export type Strategy = 'fresh' | 'remaining' | 'exam_rush'
export type ChangeType = 'moved' | 'added' | 'kept' | 'blocked' | 'cancelled'
export type ChatRole = 'user' | 'assistant'
export type ActivityCategory =
  | 'study'
  | 'work'
  | 'entertainment'
  | 'illness'
  | 'unexpected'
  | 'rest'
  | 'other'
export type ActivitySource = 'manual' | 'study_session' | 'cancelled_session'
export type MissReason =
  | 'club'
  | 'exercise'
  | 'social'
  | 'rest'
  | 'mood'
  | 'emergency'
  | 'work'
  | 'illness'
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
  long_break_minutes: number
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
  rescheduled_from_id: string | null
}

export interface PlanResponse {
  plan_id: string
  sessions: StudySession[]
  summary: string
  warnings: string[]
  unscheduled: string[]
}

export interface PrivacyResponse {
  anonymous_session: boolean
  api_version: string
  durable_storage: boolean
  retention_days: number
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
  rescheduled_from_id: string | null
}

export interface SessionCreateInput {
  subject: string
  topic: string
  start: string
  end: string
  deadline?: string | null
}

export interface SessionUpdateInput {
  subject?: string
  topic?: string
  start: string
  end: string
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
  unscheduled: string[]
  insights: Insights | null
  reschedule: RescheduleProposal | null
}

export type RescheduleStatus =
  | 'full_slot'
  | 'no_full_slot'
  | 'needs_limit_approval'
  | 'scheduled'
  | 'backlog'

export type RescheduleAction = 'accept_full' | 'split' | 'approve_limit' | 'backlog'

export interface RescheduleSlot {
  start: string
  end: string
}

export interface RescheduleProposal {
  source_session_id: string
  subject: string
  topic: string
  duration_minutes: number
  status: RescheduleStatus
  slots: RescheduleSlot[]
  extra_minutes: number
  search_through: string
  search_days: number
  chunk_minutes: number
}

export interface RescheduleResponse {
  sessions: StudySession[]
  changes: PlanChange[]
  warnings: string[]
  unscheduled: string[]
  reschedule: RescheduleProposal
}

export interface AnalyzeResponse {
  topics: Topic[]
  source: 'ai' | 'fallback'
}

export interface MaterialAnalyzeResponse extends AnalyzeResponse {
  material_name: string
  material_type: 'text' | 'markdown' | 'pdf' | 'docx' | 'url' | 'video'
  extracted_chars: number
  truncated: boolean
  transcription_source: 'ai' | null
}

export interface ActivityCategoryOption {
  value: ActivityCategory
  label: string
}

export interface ActivityLog {
  id: string
  occurred_on: string
  category: ActivityCategory
  label: string
  minutes: number
  note: string
  source: ActivitySource
  source_id: string | null
  plan_id: string | null
  created_at: string
}

export interface ActivityInput {
  occurred_on: string
  category: ActivityCategory
  label: string
  minutes: number
  note: string
}

export interface ActivityDay {
  date: string
  minutes: Record<ActivityCategory, number>
}

export interface ActivityTotal {
  category: ActivityCategory
  label: string
  minutes: number
}

export interface ActivityDashboard {
  period_start: string
  period_end: string
  days: 7 | 30
  daily: ActivityDay[]
  totals: ActivityTotal[]
  activities: ActivityLog[]
}

export interface ChatMessage {
  role: ChatRole
  content: string
}

export interface CoachResponse {
  reply: ChatMessage
  history: ChatMessage[]
  source: 'ai' | 'fallback'
  suggestions: string[]
}

export type HealthConnectionStatus = 'connected' | 'paused'
export type ReadinessStatus = 'insufficient_data' | 'ready' | 'reduce_load' | 'recovery'

export interface DailyHealthSummary {
  occurred_on: string
  sleep_minutes: number | null
  sleep_start: string | null
  sleep_end: string | null
  resting_heart_rate_bpm: number | null
  hrv_rmssd_ms: number | null
  energy_level: number | null
  feels_unwell: boolean | null
  source_devices: string[]
  synced_at: string
}

export interface ReadinessFactor {
  key: string
  label: string
  impact: 'positive' | 'neutral' | 'negative'
  detail: string
}

export interface ReadinessAssessment {
  occurred_on: string
  status: ReadinessStatus
  capacity_percent: number
  confidence: 'low' | 'medium' | 'high'
  factors: ReadinessFactor[]
  baseline_days: number
  sleep_baseline_minutes: number | null
  resting_hr_baseline_bpm: number | null
  hrv_baseline_rmssd_ms: number | null
  disclaimer: string
}

export interface HealthConnection {
  provider: 'health_connect'
  status: HealthConnectionStatus
  paired_at: string
  last_synced_at: string | null
  permissions: string[]
  sources: string[]
}

export interface HealthScheduleRecommendation {
  id: string
  kind: 'protect' | 'shorten_move' | 'recovery_break' | 'no_change'
  title: string
  detail: string
  session_id: string | null
  protected: boolean
  keep_minutes: number
  defer_minutes: number
}

export interface HealthPolicy {
  baseline_days: number
  minimum_baseline_days: number
  ready_capacity_percent: number
  reduce_capacity_percent: number
  recovery_capacity_percent: number
  retention_days: number
}

export interface HealthAdjustmentLog {
  id: string
  occurred_on: string
  readiness_status: ReadinessStatus
  changes: PlanChange[]
  applied_at: string
}

export interface HealthDashboard {
  plan_id: string
  connection: HealthConnection | null
  summaries: DailyHealthSummary[]
  readiness: ReadinessAssessment
  recommendations: HealthScheduleRecommendation[]
  adjustments: HealthAdjustmentLog[]
  policy: HealthPolicy
}

export interface HealthPairingResponse {
  plan_id: string
  provider: 'health_connect'
  code: string
  expires_at: string
}

export interface HealthScheduleApplyResponse {
  sessions: StudySession[]
  changes: PlanChange[]
  unscheduled: string[]
  readiness: ReadinessAssessment
  recommendations: HealthScheduleRecommendation[]
}
