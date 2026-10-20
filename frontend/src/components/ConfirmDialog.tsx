interface Props {
  message: string
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmDialog({ message, onCancel, onConfirm }: Props) {
  return (
    <div className="overlay">
      <div className="dialog" role="alertdialog" aria-modal="true" aria-label="삭제 확인">
        <p>{message}</p>
        <div className="dialog-actions">
          <button type="button" onClick={onCancel} autoFocus>
            취소
          </button>
          <button type="button" onClick={onConfirm}>
            삭제
          </button>
        </div>
      </div>
    </div>
  )
}
