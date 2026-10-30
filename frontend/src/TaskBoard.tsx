import { useEffect, useState } from 'react'
import {
  ApiError,
  createTask,
  deleteTask,
  listTasks,
  logout,
  updateTask,
  updateTaskStatus,
} from './api'
import { Board } from './components/Board'
import { BriefingButton } from './components/BriefingButton'
import { BriefingCard } from './components/BriefingCard'
import { CommandBar } from './components/CommandBar'
import { useBriefing } from './hooks/useBriefing'
import { WeekPlanButton } from './components/WeekPlanButton'
import { WeekPlanCard } from './components/WeekPlanCard'
import { useWeekPlan } from './hooks/useWeekPlan'
import { ConfirmDialog } from './components/ConfirmDialog'
import { TaskDialog } from './components/TaskDialog'
import type { TaskActions } from './components/TaskCard'
import type {
  GeneratedTask,
  NewTask,
  Status,
  Task,
  TaskChanges,
  User,
} from './types'

type LoadState = 'loading' | 'ready' | 'failed'

interface Props {
  user: User
  onLoggedOut: () => void
}

function TaskBoard({ user, onLoggedOut }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Task | null>(null)
  const [deleting, setDeleting] = useState<Task | null>(null)
  const [actionError, setActionError] = useState('')
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const briefing = useBriefing()
  const weekPlan = useWeekPlan()

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

  async function handleLogout() {
    try {
      await logout()
      onLoggedOut()
    } catch {
      setActionError('로그아웃하지 못했습니다. 다시 시도해 주세요.')
    }
  }

  // 정렬과 기한 초과는 서버가 정한다. 바꾼 뒤에는 서버 순서를 다시 받아 온다. (R-012)
  // 실패해도 이미 반영한 내용은 그대로 두고 다음에 불러올 때 맞춰진다.
  function refreshOrder() {
    listTasks()
      .then(setTasks)
      .catch(() => {})
  }

  async function handleCreate(task: NewTask) {
    const created = await createTask(task)
    setTasks((prev) => [...prev, created])
    setCreating(false)
    refreshOrder()
  }

  // AI 가 나눠 준 초안을 하나씩 차례로 만든다. 상태는 "할 일" 이다. 성공한 것은 보드에 남기고,
  // 만들지 못한 초안을 돌려준다. 모두 만들었으면 창을 닫고, 하나라도 못 만들었으면 열어 둔다.
  async function handleRegisterGenerated(drafts: GeneratedTask[]): Promise<GeneratedTask[]> {
    const created: Task[] = []
    const failed: GeneratedTask[] = []
    for (const [index, draft] of drafts.entries()) {
      try {
        created.push(await createTask({ ...draft, status: 'TODO' }))
      } catch (e) {
        failed.push(draft)
        // 로그인이 풀렸으면(401) 남은 것도 모두 실패한다. 더 보내지 않는다.
        if (e instanceof ApiError && e.status === 401) {
          failed.push(...drafts.slice(index + 1))
          break
        }
      }
    }
    if (created.length > 0) {
      setTasks((prev) => [...prev, ...created])
      refreshOrder()
    }
    if (failed.length === 0) {
      setCreating(false)
    }
    return failed
  }

  async function handleEdit(task: Task, values: NewTask) {
    // 바뀐 항목만 보낸다. 마감일은 사용자가 비웠을 때만 null 이 된다.
    const changes: TaskChanges = {}
    if (values.title !== task.title) changes.title = values.title
    if (values.description !== task.description) changes.description = values.description
    if (values.priority !== task.priority) changes.priority = values.priority
    if (values.due_date !== task.due_date) changes.due_date = values.due_date
    if (Object.keys(changes).length === 0) {
      setEditing(null)
      return
    }
    // 서버가 확인해 돌려준 Task 로만 화면을 바꾼다. 실패하면 창에서 안내한다.
    const updated = await updateTask(task.id, changes)
    setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)))
    setEditing(null)
    refreshOrder()
  }

  async function handleChangeStatus(id: number, status: Status) {
    try {
      const updated = await updateTaskStatus(id, status)
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
      setActionError('')
      refreshOrder()
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
        <div className="app-title">
          <h1>task-flow</h1>
          <BriefingButton
            loading={briefing.loading}
            disabled={loadState !== 'ready'}
            onClick={briefing.run}
          />
          <WeekPlanButton
            loading={weekPlan.loading}
            disabled={loadState !== 'ready'}
            onClick={weekPlan.run}
          />
        </div>
        <div className="app-header-actions">
          <span className="username">{user.username}</span>
          <button type="button" onClick={handleLogout}>
            로그아웃
          </button>
          <button
            type="button"
            onClick={() => setCreating(true)}
            disabled={loadState !== 'ready'}
          >
            생성
          </button>
        </div>
      </header>
      {briefing.briefing && (
        <BriefingCard briefing={briefing.briefing} tasks={tasks} onClose={briefing.close} />
      )}
      {briefing.message && (
        <p className={briefing.isError ? 'error' : 'briefing-note'} role="status">
          {briefing.message}
        </p>
      )}
      {weekPlan.weekPlan && <WeekPlanCard weekPlan={weekPlan.weekPlan} onClose={weekPlan.close} />}
      {weekPlan.message && (
        <p className={weekPlan.isError ? 'error' : 'weekplan-info'} role="status">
          {weekPlan.message}
        </p>
      )}
      <CommandBar tasks={tasks} disabled={loadState !== 'ready'} onApplied={refreshOrder} />
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
          onRegisterGenerated={handleRegisterGenerated}
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

export default TaskBoard
