import type { Task } from '../types'

export function TaskCard({ task }: { task: Task }) {
  return <li className="task-card">{task.title}</li>
}
