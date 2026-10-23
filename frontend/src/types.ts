// 상태 세 값은 API 가 인정하는 값과 같다. (D-007)
export const STATUSES = ['TODO', 'IN_PROGRESS', 'DONE'] as const

export type Status = (typeof STATUSES)[number]

export const STATUS_LABEL: Record<Status, string> = {
  TODO: '할 일',
  IN_PROGRESS: '진행 중',
  DONE: '완료',
}

export const TITLE_MAX_LENGTH = 20

// 카드에 보이는 설명의 최대 글자 수. 넘으면 … 으로 줄인다.
export const DESCRIPTION_PREVIEW_LENGTH = 30

export interface User {
  id: number
  username: string
}

export interface Credentials {
  username: string
  password: string
}

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
