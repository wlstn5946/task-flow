import { useEffect, useRef, useState } from 'react'
import { ApiError, getWeekPlan } from '../api'
import type { WeekPlan } from '../types'

const UNAVAILABLE = '지금은 계획을 작성할 수 없습니다'
const FAILED = '계획을 받지 못했습니다'
const EMPTY = '일정이 비어 있어요'

export interface WeekPlanState {
  /** 요청이 가는 중이다. */
  loading: boolean
  /** 받은 계획. 있으면 카드를 보인다. */
  weekPlan: WeekPlan | null
  /** 실패 또는 일정 없음 안내. 카드가 아니라 한 줄로 보인다. */
  message: string
  /** message 가 실패인지(true), 일정이 없다는 안내인지(false). */
  isError: boolean
  run: () => void
  close: () => void
}

function isWeekPlan(value: WeekPlan): boolean {
  return (
    value !== null &&
    typeof value === 'object' &&
    Array.isArray(value.plan) &&
    typeof value.note === 'string' &&
    value.plan.every(
      (item) =>
        item !== null &&
        typeof item === 'object' &&
        typeof item.date === 'string' &&
        typeof item.title === 'string',
    )
  )
}

export function useWeekPlan(): WeekPlanState {
  const [loading, setLoading] = useState(false)
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null)
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
    setWeekPlan(null)
    setMessage('')
    try {
      const result = await getWeekPlan()
      if (mine !== seq.current) return
      if (!isWeekPlan(result)) throw new Error('알 수 없는 계획')
      if (result.plan.length === 0) {
        setMessage(EMPTY)
        setIsError(false)
      } else {
        setWeekPlan(result)
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
    setWeekPlan(null)
    setMessage('')
  }

  return { loading, weekPlan, message, isError, run, close }
}
