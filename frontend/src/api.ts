import type { NewTask, Status, Task } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`요청 실패 (${res.status})`)
  }
  return (await res.json()) as T
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks')
}

export function createTask(task: NewTask): Promise<Task> {
  return request<Task>('/tasks', { method: 'POST', body: JSON.stringify(task) })
}

export function updateTaskStatus(id: number, status: Status): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}
