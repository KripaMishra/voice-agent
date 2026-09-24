export type InterviewStatus =
  | 'created'
  | 'preparing'
  | 'ready'
  | 'in_progress'
  | 'completed'

export type Track = 'resume' | 'situational' | 'discussion'

export type ChecklistStatus = 'pending' | 'asked' | 'answered'

export type TurnRole = 'agent' | 'candidate'

export interface Candidate {
  id: string
  name: string
  email: string
  resume_ref: string | null
}

export interface NewCandidate {
  name: string
  email: string
  resume_ref?: string | null
}

export interface Interview {
  id: string
  candidate_id: string
  jd_ref: string
  room_id: string | null
  status: InterviewStatus
  time_budget_s: number
  created_at: string
  started_at: string | null
  ended_at: string | null
}

export interface InterviewStarted extends Interview {
  token: string
  livekit_url: string
}

export interface NewInterview {
  candidate_id: string
  jd_ref: string
  time_budget_s?: number
}

export interface ChecklistItem {
  id: string
  track: Track
  text: string
  status: ChecklistStatus
  position: number
}

export interface Turn {
  id: string
  role: TurnRole
  text: string
  ts: string
  checklist_item_id: string | null
}

export interface TaskScore {
  checklist_item_id: string
  score: number
  rationale: string
}

export interface InterviewDetail extends Interview {
  checklist_items: ChecklistItem[]
  turns: Turn[]
  task_scores: TaskScore[]
}
