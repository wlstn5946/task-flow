import { STATUSES, type Task } from '../types'
import { Column } from './Column'
import type { TaskActions } from './TaskCard'

interface Props {
  tasks: Task[]
  actions: TaskActions
}

export function Board({ tasks, actions }: Props) {
  return (
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
  )
}
