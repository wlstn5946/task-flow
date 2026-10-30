import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, createTask, runCommand, updateTask, updateTaskStatus } from '../api'
import {
  COMMAND_MAX_LENGTH,
  PRIORITY_LABEL,
  type CommandAction,
  type Task,
} from '../types'
import './command.css'

const UNAVAILABLE = '지금은 시킬 수 없습니다'
const FAILED = '알아듣지 못했습니다'

interface Props {
  tasks: Task[]
  disabled: boolean
  /** 적용이 한 건이라도 끝난 뒤 목록을 다시 받는다. */
  onApplied: () => void
}

interface Line {
  action: CommandAction
  text: string
}

function dueText(due: string | null): string {
  return due ? `마감 ${due}` : '마감 없음'
}

// 제목은 add 만 서버 값이다. due · done 은 보드의 Task 에서 id 로 찾고, 그 사이 지워진 것은 뺀다.
function toLines(actions: CommandAction[], tasks: Task[]): Line[] {
  const byId = new Map(tasks.map((task) => [task.id, task]))
  return actions.flatMap((action): Line[] => {
    if (action.kind === 'add') {
      if (!action.title) return []
      const priority = PRIORITY_LABEL[action.priority ?? 'NORMAL']
      return [
        {
          action,
          text: `새 카드 「${action.title}」 — 우선순위 ${priority} · ${dueText(action.due_date)}`,
        },
      ]
    }
    const task = action.id === null ? undefined : byId.get(action.id)
    if (!task) return []
    if (action.kind === 'done') {
      return [{ action, text: `${task.title} — 완료로` }]
    }
    if (!action.due_date) return []
    const now = task.due_date ? `지금 마감 ${task.due_date}` : '지금 마감 없음'
    return [{ action, text: `${task.title}(${now}) — 마감을 ${action.due_date} 로` }]
  })
}

function applyAction(action: CommandAction): Promise<unknown> {
  if (action.kind === 'add') {
    return createTask({
      title: action.title ?? '',
      description: '',
      status: 'TODO',
      priority: action.priority ?? 'NORMAL',
      due_date: action.due_date,
    })
  }
  if (action.kind === 'due') return updateTask(action.id ?? 0, { due_date: action.due_date })
  return updateTaskStatus(action.id ?? 0, 'DONE')
}

export function CommandBar({ tasks, disabled, onApplied }: Props) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [actions, setActions] = useState<CommandAction[] | null>(null)
  const [ask, setAsk] = useState('')
  const [error, setError] = useState('')
  // 요청마다 번호를 매겨, 취소한 뒤나 다시 누른 뒤에 늦게 온 응답은 버린다.
  const seq = useRef(0)

  useEffect(() => {
    return () => {
      seq.current += 1
    }
  }, [])

  const lines = actions ? toLines(actions, tasks) : []
  const trimmed = text.trim()

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!trimmed || loading || applying || disabled) return
    seq.current += 1
    const mine = seq.current
    setLoading(true)
    setActions(null)
    setAsk('')
    setError('')
    try {
      const result = await runCommand(trimmed)
      if (mine !== seq.current) return
      if (!Array.isArray(result?.actions)) throw new Error('알 수 없는 응답')
      if (result.actions.length === 0) {
        setAsk(typeof result.ask === 'string' && result.ask ? result.ask : FAILED)
      } else {
        setActions(result.actions)
      }
    } catch (err) {
      if (mine !== seq.current) return
      if (err instanceof ApiError && err.status === 422 && err.detail) setError(err.detail)
      else setError(err instanceof ApiError && err.status === 503 ? UNAVAILABLE : FAILED)
    } finally {
      if (mine === seq.current) setLoading(false)
    }
  }

  function cancel() {
    seq.current += 1
    setLoading(false)
    setActions(null)
    setAsk('')
    setError('')
  }

  // 줄마다 기존 API 를 한 번씩 차례로 부른다. 성공한 줄은 카드에서 빼고 실패한 줄은 남긴다.
  async function apply() {
    setApplying(true)
    setError('')
    const failed: Line[] = []
    for (const [index, line] of lines.entries()) {
      try {
        await applyAction(line.action)
      } catch (err) {
        failed.push(line)
        // 로그인이 풀렸으면(401) 남은 것도 모두 실패한다. 더 보내지 않는다.
        if (err instanceof ApiError && err.status === 401) {
          failed.push(...lines.slice(index + 1))
          break
        }
      }
    }
    if (failed.length < lines.length) onApplied()
    if (failed.length === 0) {
      setActions(null)
      setText('')
    } else {
      setActions(failed.map((line) => line.action))
      setError(`${failed.length}개를 적용하지 못했습니다`)
    }
    setApplying(false)
  }

  return (
    <section className="command" aria-label="한 문장 명령">
      <form className="command-form" onSubmit={submit}>
        <input
          type="text"
          aria-label="시킬 일"
          placeholder="예: 내일까지 보고서 쓰기 추가해줘"
          value={text}
          maxLength={COMMAND_MAX_LENGTH}
          disabled={loading || applying}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" disabled={disabled || loading || applying || !trimmed}>
          {loading ? '알아듣는 중...' : '시키기'}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {ask && <p className="command-ask" role="status">{ask}</p>}
      {actions && (
        <div className="command-card">
          <h2>이렇게 바꿀까요? {lines.length}개</h2>
          <ul>
            {lines.map((line, index) => (
              <li key={index}>{line.text}</li>
            ))}
          </ul>
          <div className="command-actions">
            <button type="button" onClick={apply} disabled={applying || lines.length === 0}>
              {applying ? '적용 중...' : '적용'}
            </button>
            <button type="button" onClick={cancel} disabled={applying}>
              취소
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
