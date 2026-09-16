// The only module that talks HTTP. Components import from here, never fetch
// directly, so swapping transport or adding auth touches one file.

import type {
  ActivityCategoryOption,
  ActivityDashboard,
  ActivityInput,
  ActivityLog,
  AnalyzeResponse,
  CalendarEvent,
  CoachResponse,
  Completion,
  Insights,
  MaterialAnalyzeResponse,
  MissReason,
  PlanRequest,
  PlanResponse,
  PrivacyResponse,
  ProgressResponse,
  ReasonOption,
  Recall,
} from './types'

const BASE = '/api' // proxied to the backend by vite.config.ts

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    const headers = new Headers(init?.headers)
    if (!(init?.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    res = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: 'include',
      headers,
    })
  } catch {
    // Distinguish "backend is not running" from "backend said no", because the
    // fixes are different and the user needs to know which.
    throw new ApiError('Cannot reach the backend. Is the server running?', 0)
  }

  if (!res.ok) {
    let detail = res.statusText
    const contentType = res.headers.get('content-type') ?? ''
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // non-JSON error body; keep the status text
    }
    if (res.status >= 500 && !contentType.includes('application/json')) {
      detail = 'Cannot reach the StudyGrid API. Start the backend server and try again.'
    }
    throw new ApiError(detail, res.status)
  }

  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

export function createPlan(req: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/plan', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export function getLatestPlan(): Promise<PlanResponse | null> {
  return request<PlanResponse | null>('/plan/latest')
}

export function getEvents(planId: string): Promise<CalendarEvent[]> {
  return request<CalendarEvent[]>(`/plan/${planId}/events`)
}

export async function deletePlan(planId: string): Promise<void> {
  await request<void>(`/plan/${planId}`, { method: 'DELETE' })
}

export async function deleteSessionData(): Promise<void> {
  await request<void>('/session', { method: 'DELETE' })
}

export function getPrivacy(): Promise<PrivacyResponse> {
  return request<PrivacyResponse>('/privacy')
}

export function submitProgress(
  planId: string,
  sessionId: string,
  completion: Completion,
  recall: Recall | null,
  missReason: MissReason | null,
): Promise<ProgressResponse> {
  return request<ProgressResponse>('/progress', {
    method: 'POST',
    body: JSON.stringify({
      plan_id: planId,
      session_id: sessionId,
      completion,
      recall,
      miss_reason: missReason,
    }),
  })
}

/** Reason options come from the backend so the UI cannot drift out of sync. */
export function getMissReasons(): Promise<ReasonOption[]> {
  return request<ReasonOption[]>('/miss-reasons')
}

export function getInsights(planId: string): Promise<Insights> {
  return request<Insights>(`/plan/${planId}/insights`)
}

/** Extract topics from pasted course material (6.1). */
export function analyzeMaterial(subject: string, text: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify({ subject, text }),
  })
}

export function analyzeMaterialFile(
  subject: string,
  file: File,
): Promise<MaterialAnalyzeResponse> {
  const body = new FormData()
  body.set('subject', subject)
  body.set('file', file)
  return request<MaterialAnalyzeResponse>('/materials/upload', { method: 'POST', body })
}

export function analyzeMaterialUrl(
  subject: string,
  url: string,
): Promise<MaterialAnalyzeResponse> {
  return request<MaterialAnalyzeResponse>('/materials/url', {
    method: 'POST',
    body: JSON.stringify({ subject, url }),
  })
}

export function getActivityCategories(): Promise<ActivityCategoryOption[]> {
  return request<ActivityCategoryOption[]>('/activity-categories')
}

export function getActivityDashboard(days: 7 | 30, end: string): Promise<ActivityDashboard> {
  return request<ActivityDashboard>(`/activities?days=${days}&end=${encodeURIComponent(end)}`)
}

export function createActivity(input: ActivityInput): Promise<ActivityLog> {
  return request<ActivityLog>('/activities', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateActivity(id: string, input: ActivityInput): Promise<ActivityLog> {
  return request<ActivityLog>(`/activities/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export async function deleteActivity(id: string): Promise<void> {
  await request<void>(`/activities/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function sendCoachMessage(
  planId: string,
  message: string,
  sessionId: string | null,
): Promise<CoachResponse> {
  return request<CoachResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      plan_id: planId,
      message,
      session_id: sessionId,
    }),
  })
}

export { ApiError }
