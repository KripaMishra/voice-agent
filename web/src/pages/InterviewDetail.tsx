import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, describeError } from '../api'
import { Checklist, ScoreSummary } from '../components/Checklist'
import { Transcript } from '../components/Transcript'
import { ErrorNote, InfoNote, Loading, StatusPill } from '../components/ui'
import { formatBudget, formatDateTime, formatElapsed } from '../format'
import { useFetch, usePolling, useRefreshShortcut } from '../hooks'

export function InterviewDetail() {
  const { interviewId = '' } = useParams()
  const navigate = useNavigate()

  const { data, error, reload } = useFetch(async () => {
    const interview = await api.getInterview(interviewId)
    const person = await api.getCandidate(interview.candidate_id)
    return { interview, person }
  })

  useRefreshShortcut(reload)
  usePolling(data?.interview.status === 'preparing', reload)

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await action()
      reload()
    } catch (cause) {
      setActionError(describeError(cause))
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="stack">
        <ErrorNote message={error} />
        <Link to="/">Back to candidates</Link>
      </div>
    )
  }

  if (!data) {
    return <Loading label="Loading interview…" />
  }

  const { interview, person } = data
  const awaitingScores =
    interview.status === 'completed' &&
    interview.task_scores.length === 0 &&
    interview.turns.length > 0

  return (
    <div className="stack">
      <div className="row">
        <h1>Interview</h1>
        <StatusPill status={interview.status} />
        <span className="spacer" />
        <span className="hint">
          <span className="kbd">R</span> to refresh
        </span>
      </div>

      <section className="card">
        <div className="card__body">
          <dl className="meta">
            <div>
              <dt>Candidate</dt>
              <dd>
                <Link to={`/candidates/${person.id}`}>{person.name}</Link>
              </dd>
            </div>
            <div>
              <dt>Job description</dt>
              <dd>{interview.jd_ref}</dd>
            </div>
            <div>
              <dt>Budget</dt>
              <dd>{formatBudget(interview.time_budget_s)}</dd>
            </div>
            <div>
              <dt>Spoke for</dt>
              <dd>{formatElapsed(interview.started_at, interview.ended_at)}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(interview.created_at)}</dd>
            </div>
          </dl>

          <div className="row">
            {interview.status === 'ready' && (
              <button
                className="button button--primary"
                type="button"
                disabled={busy}
                onClick={() => navigate(`/interviews/${interview.id}/call`)}
              >
                Join the call
              </button>
            )}
            {interview.status === 'in_progress' && (
              <>
                <button
                  className="button button--primary"
                  type="button"
                  disabled={busy}
                  onClick={() => navigate(`/interviews/${interview.id}/call`)}
                >
                  Join the call
                </button>
                <button
                  className="button button--danger"
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => api.endInterview(interview.id))}
                >
                  End interview
                </button>
              </>
            )}
            {interview.status === 'preparing' && (
              <span className="muted">
                Building the checklist. This page refreshes itself.
              </span>
            )}
          </div>

          {actionError && <ErrorNote message={actionError} />}
          {awaitingScores && (
            <InfoNote message="Scoring runs after the session ends and may take a moment." />
          )}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h2>Checklist</h2>
          <span className="spacer" />
          <ScoreSummary scores={interview.task_scores} />
        </div>
        <Checklist items={interview.checklist_items} scores={interview.task_scores} />
      </section>

      <section className="card">
        <div className="card__header">
          <h2>Transcript</h2>
        </div>
        <Transcript turns={interview.turns} />
      </section>
    </div>
  )
}
