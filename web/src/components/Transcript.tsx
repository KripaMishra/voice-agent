import { formatClock } from '../format'
import type { Turn } from '../types'
import { Empty } from './ui'

export function Transcript({ turns }: { turns: Turn[] }) {
  if (turns.length === 0) {
    return <Empty label="Nothing was said in this session." />
  }

  return (
    <ul className="transcript">
      {turns.map((turn) => (
        <li key={turn.id}>
          <span className={['who', turn.role === 'agent' && 'who--agent'].filter(Boolean).join(' ')}>
            {turn.role === 'agent' ? 'Interviewer' : 'Candidate'}
            <time dateTime={turn.ts}>{formatClock(turn.ts)}</time>
          </span>
          <span>{turn.text}</span>
        </li>
      ))}
    </ul>
  )
}
