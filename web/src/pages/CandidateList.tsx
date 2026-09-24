import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, describeError } from '../api'
import { Empty, ErrorNote, Loading } from '../components/ui'
import { useFetch, useRefreshShortcut } from '../hooks'
import type { Candidate } from '../types'

const BLANK = { name: '', email: '', resume_ref: '' }

export function CandidateList() {
  const { data: candidates, error, loading, reload } = useFetch(api.listCandidates)
  const [draft, setDraft] = useState(BLANK)
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useRefreshShortcut(reload)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setFormError(null)
    try {
      await api.addCandidate({
        name: draft.name.trim(),
        email: draft.email.trim(),
        resume_ref: draft.resume_ref.trim() || null,
      })
      setDraft(BLANK)
      reload()
    } catch (cause) {
      setFormError(describeError(cause))
    } finally {
      setBusy(false)
    }
  }

  async function remove(candidate: Candidate) {
    if (!window.confirm(`Remove ${candidate.name} and their interviews?`)) return
    try {
      await api.removeCandidate(candidate.id)
      reload()
    } catch (cause) {
      setFormError(describeError(cause))
    }
  }

  let list: ReactNode
  if (error) {
    list = <ErrorNote message={error} />
  } else if (loading && !candidates) {
    list = <Loading label="Loading candidates…" />
  } else if (!candidates || candidates.length === 0) {
    list = <Empty label="No candidates yet. Add one above to get started." />
  } else {
    list = (
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Resume</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.id}>
              <td>
                <Link to={`/candidates/${candidate.id}`}>{candidate.name}</Link>
              </td>
              <td className="muted">{candidate.email}</td>
              <td className="muted">{candidate.resume_ref ?? '—'}</td>
              <td style={{ textAlign: 'right' }}>
                <button
                  className="button button--danger"
                  type="button"
                  onClick={() => remove(candidate)}
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  return (
    <div className="stack">
      <div className="row">
        <h1>Candidates</h1>
        <span className="spacer" />
        <span className="hint">
          <span className="kbd">R</span> to refresh
        </span>
      </div>

      <section className="card">
        <div className="card__header">
          <h2>Add a candidate</h2>
        </div>
        <div className="card__body">
          <form className="form-grid" onSubmit={submit}>
            <label className="field">
              <span>Name</span>
              <input
                className="input"
                required
                value={draft.name}
                onChange={(event) =>
                  setDraft({ ...draft, name: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Email</span>
              <input
                className="input"
                type="email"
                required
                value={draft.email}
                onChange={(event) =>
                  setDraft({ ...draft, email: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Resume reference</span>
              <input
                className="input"
                placeholder="resumes/ada.md"
                value={draft.resume_ref}
                onChange={(event) =>
                  setDraft({ ...draft, resume_ref: event.target.value })
                }
              />
            </label>
            <button className="button button--primary" type="submit" disabled={busy}>
              {busy ? 'Adding…' : 'Add candidate'}
            </button>
          </form>
          {formError && <ErrorNote message={formError} />}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h2>All candidates</h2>
        </div>
        {list}
      </section>
    </div>
  )
}
