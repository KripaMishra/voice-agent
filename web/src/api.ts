import type {
  Candidate,
  Interview,
  InterviewDetail,
  InterviewStarted,
  NewCandidate,
  NewInterview,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function describe(response: Response): Promise<string> {
  const fallback = response.statusText || `Request failed with ${response.status}`
  const body: unknown = await response.json().catch(() => null)
  if (typeof body !== 'object' || body === null) return fallback

  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) => (entry as { msg?: string }).msg)
      .filter((msg): msg is string => Boolean(msg))
    if (messages.length > 0) return messages.join(', ')
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await describe(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const api = {
  listCandidates: () => request<Candidate[]>('/candidate/list'),
  getCandidate: (id: string) => request<Candidate>(`/candidate/${id}`),
  addCandidate: (payload: NewCandidate) => post<Candidate>('/candidate/add', payload),
  removeCandidate: (id: string) =>
    request<void>(`/candidate/${id}`, { method: 'DELETE' }),
  listInterviews: (candidateId: string) =>
    request<Interview[]>(`/candidate/${candidateId}/interviews`),

  createInterview: (payload: NewInterview) =>
    post<Interview>('/interview/create', payload),
  getInterview: (id: string) => request<InterviewDetail>(`/interview/${id}`),
  startInterview: (id: string) => post<InterviewStarted>(`/interview/${id}/start`),
  endInterview: (id: string) => post<Interview>(`/interview/${id}/end`),
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
