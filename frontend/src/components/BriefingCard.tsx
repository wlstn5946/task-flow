import type { Briefing, Task } from '../types'
import './briefing.css'

interface Props {
  briefing: Briefing
  tasks: Task[]
  onClose: () => void
}

const NUMBERS = ['①', '②', '③']

export function BriefingCard({ briefing, tasks, onClose }: Props) {
  // 제목은 서버가 주지 않는다. 지금 보드의 Task 에서 id 로 찾고, 그 사이 지워진 것은 건너뛴다.
  const titles = new Map(tasks.map((task) => [task.id, task.title]))
  const top = briefing.top3.flatMap((pick, index) => {
    const title = titles.get(pick.id)
    return title === undefined ? [] : [{ ...pick, title, number: NUMBERS[index] }]
  })
  const later = briefing.later.flatMap((id) => {
    const title = titles.get(id)
    return title === undefined ? [] : [{ id, title }]
  })

  return (
    <section className="briefing-card" aria-label="오늘 브리핑">
      {top.length > 0 && (
        <div>
          <h2>먼저 할 일</h2>
          <ul>
            {top.map((item) => (
              <li key={item.id}>
                {item.number} <strong>{item.title}</strong> — {item.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {later.length > 0 && (
        <div>
          <h2>미뤄도 되는 일</h2>
          <ul>
            {later.map((item) => (
              <li key={item.id}>{item.title}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="briefing-cheer">{briefing.cheer}</p>
      <div className="briefing-actions">
        <button type="button" onClick={onClose}>
          닫기
        </button>
      </div>
    </section>
  )
}
