import { useEffect, useState } from 'react'
import { createTask, listTasks, updateTaskStatus } from './api'
import { Board } from './components/Board'
import { TaskDialog } from './components/TaskDialog'
import type { NewTask, Status, Task } from './types'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [creating, setCreating] = useState(false)
  const [actionError, setActionError] = useState('')

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

  async function handleChangeStatus(id: number, status: Status) {
    try {
      // 서버가 확인해 돌려준 Task 로만 화면을 바꾼다.
      const updated = await updateTaskStatus(id, status)
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
      setActionError('')
    } catch {
      setActionError('상태를 바꾸지 못했습니다. 다시 시도해 주세요.')
    }
  }

  return (
    <main>
      <header className="app-header">
        <h1>task-flow</h1>
        <button type="button" onClick={() => setCreating(true)}>
          생성
        </button>
      </header>
      {actionError && <p className="error">{actionError}</p>}
      <Board tasks={tasks} onChangeStatus={handleChangeStatus} />
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
