import { useEffect, useState } from 'react'
import {
  createTask,
  deleteTask,
  listTasks,
  updateTaskContent,
  updateTaskStatus,
} from './api'
import { Board } from './components/Board'
import { ConfirmDialog } from './components/ConfirmDialog'
import { TaskDialog } from './components/TaskDialog'
import type { TaskActions } from './components/TaskCard'
import type { NewTask, Status, Task } from './types'

type LoadState = 'loading' | 'ready' | 'failed'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Task | null>(null)
  const [deleting, setDeleting] = useState<Task | null>(null)
  const [actionError, setActionError] = useState('')
  const [loadState, setLoadState] = useState<LoadState>('loading')

  function load() {
    listTasks()
      .then((loaded) => {
        setTasks(loaded)
        setLoadState('ready')
      })
      .catch(() => setLoadState('failed'))
  }

  function retry() {
    setLoadState('loading')
    load()
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(task: NewTask) {
    const created = await createTask(task)
    setTasks((prev) => [...prev, created])
    setCreating(false)
  }

  async function handleEdit(task: Task, { title, description }: NewTask) {
    // 서버가 확인해 돌려준 Task 로만 화면을 바꾼다. 실패하면 창에서 안내한다.
    const updated = await updateTaskContent(task.id, { title, description })
    setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)))
    setEditing(null)
  }

  async function handleChangeStatus(id: number, status: Status) {
    try {
      const updated = await updateTaskStatus(id, status)
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
      setActionError('')
    } catch {
      setActionError('상태를 바꾸지 못했습니다. 다시 시도해 주세요.')
    }
  }

  async function handleConfirmDelete(task: Task) {
    setDeleting(null)
    try {
      await deleteTask(task.id)
      setTasks((prev) => prev.filter((t) => t.id !== task.id))
      setActionError('')
    } catch {
      setActionError('삭제하지 못했습니다. 다시 시도해 주세요.')
    }
  }

  const actions: TaskActions = {
    changeStatus: handleChangeStatus,
    edit: setEditing,
    remove: setDeleting,
  }

  return (
    <main>
      <header className="app-header">
        <h1>task-flow</h1>
        <button
          type="button"
          onClick={() => setCreating(true)}
          disabled={loadState !== 'ready'}
        >
          생성
        </button>
      </header>
      {actionError && <p className="error">{actionError}</p>}
      {loadState === 'loading' && <p role="status">불러오는 중...</p>}
      {loadState === 'failed' && (
        <div role="alert">
          <p className="error">Task 를 불러오지 못했습니다.</p>
          <button type="button" onClick={retry}>
            다시 시도
          </button>
        </div>
      )}
      {loadState === 'ready' && <Board tasks={tasks} actions={actions} />}
      {creating && (
        <TaskDialog
          onCancel={() => setCreating(false)}
          onSubmit={handleCreate}
        />
      )}
      {editing && (
        <TaskDialog
          key={editing.id}
          task={editing}
          onCancel={() => setEditing(null)}
          onSubmit={(values) => handleEdit(editing, values)}
        />
      )}
      {deleting && (
        <ConfirmDialog
          message={`"${deleting.title}" 을(를) 삭제할까요?`}
          onCancel={() => setDeleting(null)}
          onConfirm={() => handleConfirmDelete(deleting)}
        />
      )}
    </main>
  )
}

export default App
