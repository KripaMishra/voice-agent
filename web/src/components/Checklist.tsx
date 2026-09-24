import { CHECKLIST_LABELS, TRACK_LABELS } from '../format'
import type { ChecklistItem, TaskScore } from '../types'
import { Empty } from './ui'

export function Checklist({
  items,
  scores,
}: {
  items: ChecklistItem[]
  scores: TaskScore[]
}) {
  if (items.length === 0) {
    return <Empty label="No checklist yet." />
  }

  const scored = new Map(scores.map((score) => [score.checklist_item_id, score]))

  return (
    <ul className="checklist">
      {items.map((item) => {
        const score = scored.get(item.id)
        return (
          <li key={item.id}>
            <span className={`tick tick--${item.status}`} aria-hidden="true">
              ✓
            </span>
            <div className="body">
              <div className="row">
                <span className="pill">{TRACK_LABELS[item.track]}</span>
                <span className="muted">{CHECKLIST_LABELS[item.status]}</span>
              </div>
              <p className="text">{item.text}</p>
              {score && <p className="rationale">{score.rationale}</p>}
            </div>
            {score && <span className="score">{score.score}/10</span>}
          </li>
        )
      })}
    </ul>
  )
}

export function ScoreSummary({ scores }: { scores: TaskScore[] }) {
  if (scores.length === 0) return null
  const mean = scores.reduce((sum, score) => sum + score.score, 0) / scores.length
  return (
    <span className="pill pill--info">
      {mean.toFixed(1)} average over {scores.length}
    </span>
  )
}
