import { useEffect, useRef, useState } from 'react'
import { ApiError, getBriefing } from '../api'
import type { Briefing } from '../types'

const UNAVAILABLE = '지금은 브리핑을 쓸 수 없습니다'
const FAILED = '브리핑을 받지 못했습니다'
const EMPTY = '오늘은 비어 있어요'

export interface BriefingState {
  /** 요청이 가는 중이다. */
  loading: boolean
  /** 받은 브리핑. 있으면 카드를 보인다. */
  briefing: Briefing | null
  /** 실패 또는 할 일 없음 안내. 카드가 아니라 한 줄로 보인다. */
  message: string
  /** message 가 실패인지(true), 할 일이 없다는 안내인지(false). */
  isError: boolean
  run: () => void
  close: () => void
}

function isBriefing(value: Briefing): boolean {
  return (
    value !== null &&
    typeof value === 'object' &&
    Array.isArray(value.top3) &&
    Array.isArray(value.later) &&
    typeof value.cheer === 'string'
  )
}

export function useBriefing(): BriefingState {
  const [loading, setLoading] = useState(false)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  // 요청마다 번호를 매겨, 닫은 뒤나 다시 누른 뒤에 늦게 온 응답은 버린다.
  const seq = useRef(0)

  useEffect(() => {
    return () => {
      seq.current += 1
    }
  }, [])

  async function run() {
    seq.current += 1
    const mine = seq.current
    setLoading(true)
    setBriefing(null)
    setMessage('')
    try {
      const result = await getBriefing()
      if (mine !== seq.current) return
      if (!isBriefing(result)) throw new Error('알 수 없는 브리핑')
      if (result.top3.length === 0 && result.later.length === 0) {
        setMessage(EMPTY)
        setIsError(false)
      } else {
        setBriefing(result)
      }
    } catch (e) {
      if (mine !== seq.current) return
      setMessage(e instanceof ApiError && e.status === 503 ? UNAVAILABLE : FAILED)
      setIsError(true)
    } finally {
      if (mine === seq.current) setLoading(false)
    }
  }

  function close() {
    seq.current += 1
    setLoading(false)
    setBriefing(null)
    setMessage('')
  }

  return { loading, briefing, message, isError, run, close }
}
