import { useState, type FormEvent } from 'react'
import {
  STATUSES,
  STATUS_LABEL,
  TITLE_MAX_LENGTH,
  type NewTask,
  type Status,
  type Task,
} from '../types'

interface Props {
  /** 있으면 수정 창이 된다. 수정은 상태를 바꾸지 않는다. */
  task?: Task
  onCancel: () => void
  onSubmit: (task: NewTask) => Promise<void>
}

export function TaskDialog({ task, onCancel, onSubmit }: Props) {
  const editing = task !== undefined
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<Status>(task?.status ?? 'TODO')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    // 빠른 안내용 점검이다. 최종 판단은 API 가 한다. (D-003)
    if (title.trim() === '') {
      setError('제목을 입력해 주세요.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await onSubmit({ title: title.trim(), description, status })
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
