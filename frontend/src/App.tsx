import { useEffect, useState } from 'react'

function App() {
  const [apiStatus, setApiStatus] = useState('확인 중...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((body: { status: string }) => setApiStatus(body.status))
      .catch(() => setApiStatus('API에 연결할 수 없음'))
  }, [])

  return (
    <main>
      <h1>task-flow</h1>
      <p>API 상태: {apiStatus}</p>
    </main>
  )
}

export default App
