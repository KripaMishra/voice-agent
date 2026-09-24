import { STATUS_LABELS } from '../format'
import type { InterviewStatus } from '../types'

const TONE: Record<InterviewStatus, string> = {
  created: '',
  preparing: 'pill--warn',
  ready: 'pill--info',
  in_progress: 'pill--info pill--live',
  completed: 'pill--ok',
}

export function StatusPill({ status }: { status: InterviewStatus }) {
  return (
    <span className={['pill', TONE[status]].filter(Boolean).join(' ')}>
      {STATUS_LABELS[status]}
    </span>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="note note--error" role="alert">
      {message}
    </p>
  )
}

export function InfoNote({ message }: { message: string }) {
  return <p className="note note--info">{message}</p>
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <p className="empty">{label}</p>
}

export function Empty({ label }: { label: string }) {
  return <p className="empty">{label}</p>
}
