import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, describeError } from '../api'
import { Empty, ErrorNote, Loading, StatusPill } from '../components/ui'
import { formatBudget, formatDateTime } from '../format'
import { useFetch, useRefreshShortcut } from '../hooks'

export function CandidateDetail() {
  const { candidateId = '' } = useParams()
  const navigate = useNavigate()

  const candidate = useFetch(() => api.getCandidate(candidateId))
  const interviews = useFetch(() => api.listInterviews(candidateId))
  useRefreshShortcut(() => {
    candidate.reload()
    interviews.reload()
  })

  const [jdRef, setJdRef] = useState('')
  const [budget, setBudget] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.createInterview({
        candidate_id: candidateId,
        jd_ref: jdRef.trim(),
        ...(budget.trim() ? { time_budget_s: Number(budget) } : {}),
      })
      navigate(`/interviews/${created.id}`)
    } catch (cause) {
      setError(describeError(cause))
      setBusy(false)
    }
  }

  if (candidate.error) {
    return (
      <div className="stack">
        <ErrorNote message={candidate.error} />
        <Link to="/">Back to candidates</Link>
      </div>
    )
  }

  if (!candidate.data) {
    return <Loading label="Loading candidate…" />
  }

  const person = candidate.data

  return (
    <div className="stack">
      <div className="row">
        <h1>{person.name}</h1>
        <span className="spacer" />
        <span className="hint">
          <span className="kbd">R</span> to refresh
        </span>
      </div>

      <section className="card">
        <div className="card__body">
          <dl className="meta">
            <div>
              <dt>Email</dt>
              <dd>{person.email}</dd>
            </div>
            <div>
              <dt>Resume</dt>
              <dd>{person.resume_ref ?? 'not attached'}</dd>
            </div>
            <div>
              <dt>Interviews</dt>
              <dd>{interviews.data?.length ?? 0}</dd>
            </div>
          </dl>
          {!person.resume_ref && (
            <p className="muted">
              Checklist generation needs a resume, so interviews for this candidate
              will stall in preparing until one is attached.
            </p>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h2>Start a new interview</h2>
        </div>
        <div className="card__body">
          <form className="form-grid" onSubmit={submit}>
            <label className="field">
              <span>Job description reference</span>
              <input
                className="input"
                required
                placeholder="jd/backend-engineer.md"
                value={jdRef}
                onChange={(event) => setJdRef(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Budget in seconds</span>
              <input
                className="input"
                type="number"
                min={1}
                placeholder="default"
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
            </label>
            <button className="button button--primary" type="submit" disabled={busy}>
              {busy ? 'Creating…' : 'Create interview'}
            </button>
          </form>
          {error && <ErrorNote message={error} />}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h2>Interviews</h2>
        </div>
        {interviews.error ? (
          <ErrorNote message={interviews.error} />
        ) : !interviews.data || interviews.data.length === 0 ? (
          <Empty label="No interviews yet." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Job description</th>
                <th>Budget</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {interviews.data.map((interview) => (
                <tr key={interview.id}>
                  <td>
                    <StatusPill status={interview.status} />
                  </td>
                  <td className="muted">{interview.jd_ref}</td>
                  <td className="muted">{formatBudget(interview.time_budget_s)}</td>
                  <td className="muted">{formatDateTime(interview.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Link to={`/interviews/${interview.id}`}>Open</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
