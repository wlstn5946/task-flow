import { useEffect, useState } from 'react'
import { createTask, listTasks } from './api'
import { Board } from './components/Board'
import { TaskDialog } from './components/TaskDialog'
import type { NewTask, Task } from './types'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    listTasks()
      .then(setTasks)
      .catch(() => {
        // 불러오기 실패 화면은 이슈 #4 에서 다룬다.
      })
  }, [])

  async function handleCreate(task: NewTask) {
    const created = await createTask(task)
    setTasks((prev) => [...prev, created])
    setCreating(false)
  }

  return (
    <main>
      <header className="app-header">
        <h1>task-flow</h1>
        <button type="button" onClick={() => setCreating(true)}>
          생성
        </button>
      </header>
      <Board tasks={tasks} />
      {creating && (
        <TaskDialog
          onCancel={() => setCreating(false)}
          onSubmit={handleCreate}
        />
      )}
    </main>
  )
}

export default App
