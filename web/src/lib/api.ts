// The only module that talks HTTP. Components import from here, never fetch
// directly, so swapping transport or adding auth touches one file.

import type {
  AnalyzeResponse,
  CalendarEvent,
  Completion,
  Insights,
  MissReason,
  PlanRequest,
  PlanResponse,
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
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    // Distinguish "backend is not running" from "backend said no", because the
    // fixes are different and the user needs to know which.
    throw new ApiError('Cannot reach the backend. Is the server running?', 0)
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(detail, res.status)
  }

  return res.json() as Promise<T>
}

export function createPlan(req: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/plan', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export function getEvents(planId: string): Promise<CalendarEvent[]> {
  return request<CalendarEvent[]>(`/plan/${planId}/events`)
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

export { ApiError }
