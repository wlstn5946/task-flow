import './weekplan.css'

interface Props {
  loading: boolean
  disabled: boolean
  onClick: () => void
}

export function WeekPlanButton({ loading, disabled, onClick }: Props) {
  return (
    <button type="button" onClick={onClick} disabled={disabled || loading}>
      {loading ? '만드는 중...' : '이번 주 계획'}
    </button>
  )
}
