import { useState, type FormEvent } from 'react'
import { PRIORITIES, PRIORITY_LABEL, type Priority } from '../types'
import './search.css'

export interface SearchCriteria {
  q: string
  priority: Priority | ''
}

export const NO_CRITERIA: SearchCriteria = { q: '', priority: '' }

export function hasCriteria(criteria: SearchCriteria): boolean {
  return criteria.q !== '' || criteria.priority !== ''
}

interface Props {
  disabled: boolean
  /** 조건이 있을 때만 값이 있다. 검색 결과의 개수이다. */
  resultCount: number | null
  onSearch: (criteria: SearchCriteria) => void
  onClear: () => void
}

export function SearchBar({ disabled, resultCount, onSearch, onClear }: Props) {
  const [q, setQ] = useState('')
  const [priority, setPriority] = useState<Priority | ''>('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch({ q, priority })
  }

  function handleClear() {
    setQ('')
    setPriority('')
    onClear()
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit} role="search">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="제목이나 설명에서 찾기"
        aria-label="검색어"
        disabled={disabled}
      />
      <select
        value={priority}
        onChange={(e) => setPriority(e.target.value as Priority | '')}
        aria-label="우선순위"
        disabled={disabled}
      >
        <option value="">전체</option>
        {PRIORITIES.slice()
          .reverse()
          .map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
      </select>
      <button type="submit" disabled={disabled}>
        찾기
      </button>
      <button type="button" onClick={handleClear} disabled={disabled}>
        모두 보기
      </button>
      {resultCount !== null && (
        <span className="search-count" role="status">
          검색 결과 {resultCount}개
        </span>
      )}
    </form>
  )
}
