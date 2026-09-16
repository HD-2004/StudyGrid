import type {
  AnalyzeResponse,
  CalendarEvent,
  Completion,
  PlanRequest,
  PlanResponse,
  ProgressResponse,
  Recall,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(
  /\/$/,
  '',
)

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(
      'StudyGrid could not reach the planning service. Check that the API is running on port 8000.',
      0,
    )
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      if (typeof body.detail === 'string') message = body.detail
      if (Array.isArray(body.detail)) {
        message = body.detail.map((item) => item.msg).filter(Boolean).join(' ')
      }
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new ApiError(message, response.status)
  }

  return (await response.json()) as T
}

export function analyzeMaterial(subject: string, text: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({ subject, text }),
  })
}

export function createPlan(payload: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/api/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getEvents(planId: string): Promise<CalendarEvent[]> {
  return request<CalendarEvent[]>(`/api/plan/${planId}/events`)
}

export function submitProgress(payload: {
  plan_id: string
  session_id: string
  completion: Completion
  recall: Recall | null
}): Promise<ProgressResponse> {
  return request<ProgressResponse>('/api/progress', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getApiBaseUrl(): string {
  return API_BASE_URL
}
