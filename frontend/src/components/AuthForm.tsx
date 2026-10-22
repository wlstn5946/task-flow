import { useState, type FormEvent } from 'react'
import { ApiError, login, register } from '../api'
import type { User } from '../types'

interface Props {
  onLoggedIn: (user: User) => void
}

type Mode = 'login' | 'register'

function messageFor(mode: Mode, error: unknown): string {
  if (error instanceof ApiError) {
    if (mode === 'login' && error.status === 401) {
      return '아이디 또는 비밀번호가 맞지 않습니다.'
    }
    if (mode === 'register' && error.status === 409) {
      return '이미 쓰는 아이디입니다.'
    }
    if (mode === 'register' && error.status === 422) {
      return '아이디는 영문 · 숫자 · _ 로 3~20글자, 비밀번호는 8글자 이상이어야 합니다.'
    }
  }
  return '요청하지 못했습니다. 다시 시도해 주세요.'
}

export function AuthForm({ onLoggedIn }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function switchMode(next: Mode) {
    setMode(next)
    setError('')
    setNotice('')
    setPassword('')
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    // 빠른 안내용 점검이다. 최종 판단은 API 가 한다. (D-003)
    if (username.trim() === '' || password === '') {
      setError('아이디와 비밀번호를 입력해 주세요.')
      return
    }
    setError('')
    setNotice('')
    setSubmitting(true)
    const credentials = { username: username.trim(), password }
    try {
      if (mode === 'register') {
        // 가입해도 로그인된 상태가 되지 않는다. 따로 로그인한다. (D-016)
        await register(credentials)
        setMode('login')
        setPassword('')
        setNotice('가입했습니다. 로그인해 주세요.')
      } else {
        onLoggedIn(await login(credentials))
        return
      }
    } catch (err) {
      setError(messageFor(mode, err))
    }
    setSubmitting(false)
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h2>{mode === 'login' ? '로그인' : '가입'}</h2>
      <label>
        아이디
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
        />
      </label>
      <label>
        비밀번호
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />
      </label>
      {notice && <p role="status">{notice}</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="dialog-actions">
        <button
          type="button"
          onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
          disabled={submitting}
        >
          {mode === 'login' ? '가입' : '로그인'}
        </button>
        <button type="submit" disabled={submitting}>
          {mode === 'login' ? '로그인' : '가입'}
        </button>
      </div>
    </form>
  )
}
