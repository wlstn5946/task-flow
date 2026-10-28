// 상태 세 값은 API 가 인정하는 값과 같다. (D-007)
export const STATUSES = ['TODO', 'IN_PROGRESS', 'DONE'] as const

export type Status = (typeof STATUSES)[number]

export const STATUS_LABEL: Record<Status, string> = {
  TODO: '할 일',
  IN_PROGRESS: '진행 중',
  DONE: '완료',
}

// 우선순위 세 값은 API 가 인정하는 값과 같다. 기본값은 NORMAL 이고 비울 수 없다. (R-010)
export const PRIORITIES = ['LOW', 'NORMAL', 'HIGH'] as const

export type Priority = (typeof PRIORITIES)[number]

export const PRIORITY_LABEL: Record<Priority, string> = {
  LOW: '낮음',
  NORMAL: '보통',
  HIGH: '높음',
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
  priority: Priority
  /** YYYY-MM-DD. 마감일이 없으면 null. */
  due_date: string | null
  /** 서버가 계산해 준다. 화면은 계산하지 않는다. (R-011) */
  is_overdue: boolean
  created_at: string
  updated_at: string
}

export interface NewTask {
  title: string
  description: string
  status: Status
  priority: Priority
  due_date: string | null
}

/** AI 제안 요청. 아직 저장하지 않은 제목과 설명을 보낸다. */
export interface SuggestRequest {
  title: string
  description: string
}

/** AI 제안. 저장되지 않는다. 칸에 채우기만 하고 저장은 사용자가 한다. */
export interface Suggestion {
  priority: Priority
  /** YYYY-MM-DD. 근거가 없으면 null. */
  due_date: string | null
  reason: string
}

/** 수정 요청. 보낸 항목만 바뀐다. due_date 의 null 은 마감일 지우기이다. */
export interface TaskChanges {
  title?: string
  description?: string
  priority?: Priority
  due_date?: string | null
}
