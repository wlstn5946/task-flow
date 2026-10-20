import { STATUS_LABEL, type Status, type Task } from '../types'
import { TaskCard } from './TaskCard'

interface Props {
  status: Status
  tasks: Task[]
  onChangeStatus: (id: number, status: Status) => void
}

export function Column({ status, tasks, onChangeStatus }: Props) {
  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const id = Number(e.dataTransfer.getData('text/plain'))
    const dropped = tasks.some((task) => task.id === id)
    // 같은 열에 놓으면 아무것도 바꾸지 않는다.
    if (Number.isInteger(id) && !dropped) {
      onChangeStatus(id, status)
    }
  }

  return (
    <section
      className="column"
      aria-label={STATUS_LABEL[status]}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      <h2>{STATUS_LABEL[status]}</h2>
      <ul className="column-list">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onChangeStatus={onChangeStatus} />
        ))}
      </ul>
    </section>
  )
}
