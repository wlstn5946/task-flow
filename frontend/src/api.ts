import type {
  Briefing,
  Credentials,
  GeneratedTasks,
  GenerateRequest,
  NewTask,
  Status,
  SuggestRequest,
  Suggestion,
  Task,
  TaskChanges,
  User,
  WeekPlan,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number) {
    super(`요청 실패 (${status})`)
    this.status = status
  }
}

// 로그인이 풀렸거나 만료된 응답(401)을 받으면 화면이 로그인 화면으로 돌아가게 알린다.
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    // 로그인 실패(401)는 로그인이 풀린 것이 아니므로 제외한다.
    if (res.status === 401 && path !== '/auth/login') {
      unauthorizedHandler?.()
    }
    throw new ApiError(res.status)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}

export function register(credentials: Credentials): Promise<User> {
  return request<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function login(credentials: Credentials): Promise<User> {
  return request<User>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function fetchMe(): Promise<User> {
  return request<User>('/auth/me')
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks')
}

export function createTask(task: NewTask): Promise<Task> {
  return request<Task>('/tasks', { method: 'POST', body: JSON.stringify(task) })
}

/** 제안만 받는다. 서버는 저장하지 않는다. 실패는 ApiError(502 제안 실패 · 503 AI 꺼짐 또는 바쁨)이다. */
export function suggestTask(body: SuggestRequest): Promise<Suggestion> {
  return request<Suggestion>('/tasks/suggest', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** 목표 하나를 할 일 3~5개 초안으로 받는다. 서버는 저장하지 않는다. 실패는 ApiError(502 제안 실패 · 503 AI 꺼짐 또는 바쁨)이다. */
export function generateTasks(body: GenerateRequest): Promise<GeneratedTasks> {
  return request<GeneratedTasks>('/tasks/generate', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** 로그인한 사람의 완료 아닌 할 일로 오늘 브리핑을 받는다. 본문 없음. 실패는 ApiError(502 형식 위반 · 503 AI 꺼짐 또는 바쁨)이다. */
export function getBriefing(): Promise<Briefing> {
  return request<Briefing>('/tasks/briefing', { method: 'POST' })
}

/** 로그인한 사람의 완료 아닌 할 일을 오늘부터 7일에 나눈 이번 주 계획을 받는다. 본문 없음. 실패는 ApiError(502 형식 위반 · 503 AI 꺼짐 또는 바쁨)이다. */
export function getWeekPlan(): Promise<WeekPlan> {
  return request<WeekPlan>('/tasks/weekplan', { method: 'POST' })
}

export function updateTask(id: number, changes: TaskChanges): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
}

export function deleteTask(id: number): Promise<void> {
  return request<void>(`/tasks/${id}`, { method: 'DELETE' })
}

export function updateTaskStatus(id: number, status: Status): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}
