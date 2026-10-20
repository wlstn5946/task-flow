import { useState } from 'react'
import { STATUSES, STATUS_LABEL, type Status, type Task } from '../types'

interface Props {
  task: Task
  onChangeStatus: (id: number, status: Status) => void
}

export function TaskCard({ task, onChangeStatus }: Props) {
  const [choosing, setChoosing] = useState(false)

  function choose(status: Status) {
    setChoosing(false)
    onChangeStatus(task.id, status)
  }

  return (
    <li
      className="task-card"
      draggable
      onDragStart={(e) => e.dataTransfer.setData('text/plain', String(task.id))}
    >
      <span className="task-title">{task.title}</span>
      {choosing &&
        STATUSES.filter((s) => s !== task.status).map((s) => (
          <button key={s} type="button" onClick={() => choose(s)}>
            {STATUS_LABEL[s]}
          </button>
        ))}
      <button type="button" onClick={() => setChoosing((v) => !v)}>
        상태 변경
      </button>
    </li>
  )
}
