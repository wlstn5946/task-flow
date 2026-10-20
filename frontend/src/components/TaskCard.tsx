import { useState } from 'react'
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
  const [choosing, setChoosing] = useState(false)

  function choose(status: Status) {
    setChoosing(false)
    actions.changeStatus(task.id, status)
  }

  return (
    <li
      className="task-card"
      draggable
      onDragStart={(e) => e.dataTransfer.setData('text/plain', String(task.id))}
    >
      <span className="task-title">{task.title}</span>
      <div className="task-actions">
        {choosing &&
          STATUSES.filter((s) => s !== task.status).map((s) => (
            <button key={s} type="button" onClick={() => choose(s)}>
              {STATUS_LABEL[s]}
            </button>
          ))}
        <button type="button" onClick={() => setChoosing((v) => !v)}>
          상태 변경
        </button>
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
