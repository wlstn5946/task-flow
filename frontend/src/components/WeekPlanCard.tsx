import type { WeekPlan } from '../types'
import './weekplan.css'

interface Props {
  weekPlan: WeekPlan
  onClose: () => void
}

export function WeekPlanCard({ weekPlan, onClose }: Props) {
  return (
    <section className="weekplan-card" aria-label="이번 주 계획">
      <h2>이번 주 계획</h2>
      <table className="weekplan-table">
        <thead>
          <tr>
            <th scope="col">날짜</th>
            <th scope="col">제목</th>
          </tr>
        </thead>
        <tbody>
          {weekPlan.plan.map((item) => (
            <tr key={item.id}>
              <td className="weekplan-date">{item.date}</td>
              <td>{item.title}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {weekPlan.note && <p className="weekplan-note">{weekPlan.note}</p>}
      <div className="weekplan-actions">
        <button type="button" onClick={onClose}>
          닫기
        </button>
      </div>
    </section>
  )
}
