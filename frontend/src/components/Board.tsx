import { STATUSES, type Status, type Task } from '../types'
import { Column } from './Column'

interface Props {
  tasks: Task[]
  onChangeStatus: (id: number, status: Status) => void
}

export function Board({ tasks, onChangeStatus }: Props) {
  return (
    <div className="board">
      {STATUSES.map((status) => (
        <Column
          key={status}
          status={status}
          tasks={tasks.filter((task) => task.status === status)}
          onChangeStatus={onChangeStatus}
        />
      ))}
    </div>
  )
}
