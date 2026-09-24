import type { ChecklistStatus, InterviewStatus, Track } from './types'

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const clockFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'medium' })

export function formatDateTime(value: string | null): string {
  return value ? dateTimeFormat.format(new Date(value)) : '—'
}

export function formatClock(value: string): string {
  return clockFormat.format(new Date(value))
}

export function formatBudget(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  return `${Math.round(seconds / 60)} min`
}

export function formatElapsed(
  startedAt: string | null,
  endedAt: string | null,
): string {
  if (!startedAt) return '—'
  const stop = endedAt ? new Date(endedAt) : new Date()
  const seconds = Math.max(
    0,
    Math.round((stop.getTime() - new Date(startedAt).getTime()) / 1000),
  )
  const minutes = Math.floor(seconds / 60)
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`
}

export const STATUS_LABELS: Record<InterviewStatus, string> = {
  created: 'Created',
  preparing: 'Preparing',
  ready: 'Ready',
  in_progress: 'In progress',
  completed: 'Completed',
}

export const CHECKLIST_LABELS: Record<ChecklistStatus, string> = {
  pending: 'Not asked',
  asked: 'Asked',
  answered: 'Answered',
}

export const TRACK_LABELS: Record<Track, string> = {
  resume: 'Resume',
  situational: 'Situational',
  discussion: 'Discussion',
}
