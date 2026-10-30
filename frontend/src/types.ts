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

/** AI 할 일 나누기 요청. 이루고 싶은 목표의 제목 하나를 보낸다. */
export interface GenerateRequest {
  title: string
}

/** AI 가 나눠 준 할 일 하나. 저장 전의 초안이라 id 와 상태가 없다. */
export interface GeneratedTask {
  title: string
  description: string
  priority: Priority
  /** YYYY-MM-DD. 근거가 없으면 null. */
  due_date: string | null
}

/** AI 할 일 나누기 응답. 3~5개이며 서버는 저장하지 않는다. */
export interface GeneratedTasks {
  tasks: GeneratedTask[]
}

/** 오늘 브리핑에서 먼저 할 일 하나. 제목은 없고 id 로 Task 를 찾아 보여 준다. */
export interface BriefingPick {
  id: number
  reason: string
}

/** 오늘 브리핑. 서버는 저장하지 않는다. 할 일이 없으면 top3 · later 가 모두 빈 배열이다. */
export interface Briefing {
  top3: BriefingPick[]
  /** 미뤄도 되는 Task 의 id. */
  later: number[]
  cheer: string
}

/** 수정 요청. 보낸 항목만 바뀐다. due_date 의 null 은 마감일 지우기이다. */
export interface TaskChanges {
  title?: string
  description?: string
  priority?: Priority
  due_date?: string | null
}

/** 이번 주 계획의 한 칸. date 는 서버가 만든 한국어 날짜 글(10월 30일 (금))이고 title 은 서버가 준 값을 그대로 쓴다. */
export interface WeekPlanItem {
  id: number
  date: string
  title: string
}

/** 이번 주 계획. 서버는 저장하지 않는다. 할 일이 없으면 plan 이 빈 배열이고 note 는 빈 문자열이다. */
export interface WeekPlan {
  plan: WeekPlanItem[]
  /** 이번 주 일정 전체에 대한 한 줄 조언. */
  note: string
}
