import {
  DESCRIPTION_PREVIEW_LENGTH,
  STATUSES,
  STATUS_LABEL,
  type Status,
  type Task,
} from '../types'

// 줄바꿈은 공백으로 이어 한 줄로 만들고, 글자 수를 넘으면 … 으로 줄인다.
function previewDescription(description: string): string {
  const chars = Array.from(description.replace(/\s+/g, ' ').trim())
  if (chars.length <= DESCRIPTION_PREVIEW_LENGTH) return chars.join('')
  return chars.slice(0, DESCRIPTION_PREVIEW_LENGTH).join('') + '…'
}

export interface TaskActions {
  changeStatus: (id: number, status: Status) => void
  edit: (task: Task) => void
  remove: (task: Task) => void
}

interface Props {
  task: Task
  actions: TaskActions
}

export function TaskCard({ task, actions }: Props) {
  return (
    <li
      className="task-card"
      draggable
      onDragStart={(e) => e.dataTransfer.setData('text/plain', String(task.id))}
    >
      <div className="task-text">
        <span className="task-title">{task.title}</span>
        <span className="task-description">
          {previewDescription(task.description)}
        </span>
      </div>
      <div className="task-actions">
        <select
          aria-label="상태"
          value={task.status}
          onChange={(e) => actions.changeStatus(task.id, e.target.value as Status)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => actions.edit(task)}>
          수정
        </button>
        <button type="button" onClick={() => actions.remove(task)}>
          삭제
        </button>
      </div>
    </li>
  )
}
