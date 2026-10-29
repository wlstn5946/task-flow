import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, suggestTask } from '../api'
import {
  PRIORITIES,
  PRIORITY_LABEL,
  STATUSES,
  STATUS_LABEL,
  TITLE_MAX_LENGTH,
  type NewTask,
  type Priority,
  type Status,
  type Task,
} from '../types'

interface Props {
  /** 있으면 수정 창이 된다. 수정은 상태를 바꾸지 않는다. */
  task?: Task
  onCancel: () => void
  onSubmit: (task: NewTask) => Promise<void>
}

const SUGGEST_UNAVAILABLE = '지금은 AI 제안을 쓸 수 없습니다. 직접 입력해 주세요.'
const SUGGEST_FAILED = '제안을 못 받았습니다. 다시 제안 버튼을 눌러 보세요.'

export function TaskDialog({ task, onCancel, onSubmit }: Props) {
  const editing = task !== undefined
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<Status>(task?.status ?? 'TODO')
  const [priority, setPriority] = useState<Priority>(task?.priority ?? 'NORMAL')
  // 날짜 입력은 마감일이 없으면 빈 글자이다.
  const [dueDate, setDueDate] = useState(task?.due_date ?? '')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // AI 제안은 칸을 채우기만 한다. 저장은 [생성]/[저장] 이 따로 한다.
  const [suggesting, setSuggesting] = useState(false)
  const [suggestMessage, setSuggestMessage] = useState('')
  const [reason, setReason] = useState('')
  // 요청마다 번호를 매겨, 저장을 누른 뒤나 창이 닫힌 뒤에 늦게 온 응답은 버린다.
  const suggestSeq = useRef(0)

  useEffect(() => {
    return () => {
      suggestSeq.current += 1
    }
  }, [])

  async function handleSuggest() {
    if (title.trim() === '') {
      setReason('')
      setSuggestMessage('제목을 입력해 주세요.')
      return
    }
    suggestSeq.current += 1
    const seq = suggestSeq.current
    setSuggesting(true)
    setSuggestMessage('')
    setReason('')
    try {
      const suggestion = await suggestTask({ title: title.trim(), description })
      if (seq !== suggestSeq.current) return
      // 모르는 값이 오면 칸을 바꾸지 않고 실패로 본다.
      if (!PRIORITIES.includes(suggestion.priority)) {
        throw new Error('알 수 없는 우선순위')
      }
      setPriority(suggestion.priority)
      setDueDate(suggestion.due_date ?? '')
      setReason(suggestion.reason)
    } catch (e) {
      if (seq !== suggestSeq.current) return
      setSuggestMessage(
        e instanceof ApiError && e.status === 503 ? SUGGEST_UNAVAILABLE : SUGGEST_FAILED,
      )
    } finally {
      if (seq === suggestSeq.current) setSuggesting(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    // 빠른 안내용 점검이다. 최종 판단은 API 가 한다. (D-003)
    if (title.trim() === '') {
      setError('제목을 입력해 주세요.')
      return
    }
    setError('')
    // 제안이 아직 오는 중이어도 저장은 막지 않는다. 늦게 온 제안은 버린다.
    suggestSeq.current += 1
    setSuggesting(false)
    setSubmitting(true)
    try {
      await onSubmit({
        title: title.trim(),
        description,
        status,
        priority,
        due_date: dueDate === '' ? null : dueDate,
      })
    } catch {
      setError(
        editing
          ? '저장하지 못했습니다. 다시 시도해 주세요.'
          : 'Task 를 만들지 못했습니다. 다시 시도해 주세요.',
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="overlay">
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={editing ? 'Task 수정' : 'Task 생성'}
        onSubmit={handleSubmit}
      >
        <label>
          제목
          <input
            value={title}
            maxLength={TITLE_MAX_LENGTH}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
          />
        </label>
        <label>
          설명
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <div className="suggest-row">
          <button type="button" onClick={handleSuggest} disabled={suggesting}>
            AI 제안
          </button>
          {suggesting && (
            <span className="suggest-status" role="status">
              제안을 받는 중...
            </span>
          )}
        </div>
        {suggestMessage && <p className="error">{suggestMessage}</p>}
        <label>
          우선순위
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABEL[p]}
              </option>
            ))}
          </select>
        </label>
        <label>
          마감일 (선택)
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </label>
        {reason && (
          <p className="suggest-reason" title={reason}>
            AI 제안 이유: {reason}
          </p>
        )}
        {!editing && (
          <label>
            상태
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as Status)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onCancel} disabled={submitting}>
            취소
          </button>
          <button type="submit" disabled={submitting}>
            {editing ? '저장' : '생성'}
          </button>
        </div>
      </form>
    </div>
  )
}
