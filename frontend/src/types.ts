// 상태 세 값은 API 가 인정하는 값과 같다. (D-007)
export const STATUSES = ['TODO', 'IN_PROGRESS', 'DONE'] as const

export type Status = (typeof STATUSES)[number]

export const STATUS_LABEL: Record<Status, string> = {
  TODO: '할 일',
  IN_PROGRESS: '진행 중',
  DONE: '완료',
}

export const TITLE_MAX_LENGTH = 30

export interface Task {
  id: number
  title: string
  description: string
  status: Status
  created_at: string
  updated_at: string
}

export interface NewTask {
  title: string
  description: string
  status: Status
}
