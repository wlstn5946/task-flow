import type {
  Credentials,
  NewTask,
  Status,
  Task,
  TaskChanges,
  User,
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
