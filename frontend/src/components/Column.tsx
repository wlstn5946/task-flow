import { STATUS_LABEL, type Status, type Task } from '../types'
import { TaskCard } from './TaskCard'

export function Column({ status, tasks }: { status: Status; tasks: Task[] }) {
  return (
    <section className="column" aria-label={STATUS_LABEL[status]}>
      <h2>{STATUS_LABEL[status]}</h2>
      <ul className="column-list">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </ul>
    </section>
  )
}
