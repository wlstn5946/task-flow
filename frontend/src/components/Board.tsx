import { STATUSES, type Task } from '../types'
import { Column } from './Column'

export function Board({ tasks }: { tasks: Task[] }) {
  return (
    <div className="board">
      {STATUSES.map((status) => (
        <Column
          key={status}
          status={status}
          tasks={tasks.filter((task) => task.status === status)}
        />
      ))}
    </div>
  )
}
