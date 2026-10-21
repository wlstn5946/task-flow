import { STATUSES, STATUS_LABEL, type Status, type Task } from '../types'

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
      <span className="task-title">{task.title}</span>
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
