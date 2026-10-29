import './briefing.css'

interface Props {
  loading: boolean
  disabled: boolean
  onClick: () => void
}

export function BriefingButton({ loading, disabled, onClick }: Props) {
  return (
    <button type="button" onClick={onClick} disabled={disabled || loading}>
      {loading ? '만드는 중...' : '오늘 브리핑'}
    </button>
  )
}
