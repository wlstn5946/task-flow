import { STATUSES, type Task } from '../types'
import { Column } from './Column'
import type { TaskActions } from './TaskCard'

interface Props {
  tasks: Task[]
  actions: TaskActions
}

export function Board({ tasks, actions }: Props) {
  return (
    <>
      {tasks.length === 0 && <p className="empty">비어 있습니다.</p>}
      <div className="board">
        {STATUSES.map((status) => (
          <Column
            key={status}
            status={status}
            tasks={tasks.filter((task) => task.status === status)}
            actions={actions}
          />
        ))}
      </div>
    </>
  )
}
