import { useEffect, useState } from 'react'
import { ApiError, fetchMe, setUnauthorizedHandler } from './api'
import { AuthForm } from './components/AuthForm'
import TaskBoard from './TaskBoard'
import type { User } from './types'

type AuthState =
  | { kind: 'checking' }
  | { kind: 'failed' }
  | { kind: 'out' }
  | { kind: 'in'; user: User }

function App() {
  const [auth, setAuth] = useState<AuthState>({ kind: 'checking' })

  function checkLogin() {
    fetchMe()
      .then((user) => setAuth({ kind: 'in', user }))
      .catch((err) =>
        setAuth(
          err instanceof ApiError && err.status === 401
            ? { kind: 'out' }
            : { kind: 'failed' },
        ),
      )
  }

  function retry() {
    setAuth({ kind: 'checking' })
    checkLogin()
  }

  useEffect(() => {
    // 로그인이 풀리거나 만료되면 어느 요청에서든 로그인 화면으로 돌아간다.
    setUnauthorizedHandler(() => setAuth({ kind: 'out' }))
    checkLogin()
    return () => setUnauthorizedHandler(null)
  }, [])

  if (auth.kind === 'in') {
    // 사용자가 바뀌면 이전 사용자의 Task 가 남지 않도록 새로 만든다.
    return (
      <TaskBoard
        key={auth.user.id}
        user={auth.user}
        onLoggedOut={() => setAuth({ kind: 'out' })}
      />
    )
  }

  return (
    <main>
      <header className="app-header">
        <h1>task-flow</h1>
      </header>
      {auth.kind === 'checking' && <p role="status">불러오는 중...</p>}
      {auth.kind === 'failed' && (
        <div role="alert">
          <p className="error">서버에 연결하지 못했습니다.</p>
          <button type="button" onClick={retry}>
            다시 시도
          </button>
        </div>
      )}
      {auth.kind === 'out' && (
        <AuthForm onLoggedIn={(user) => setAuth({ kind: 'in', user })} />
      )}
    </main>
  )
}

export default App
