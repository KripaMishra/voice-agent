import { Suspense, lazy } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { Loading } from './components/ui'
import { CandidateDetail } from './pages/CandidateDetail'
import { CandidateList } from './pages/CandidateList'
import { InterviewDetail } from './pages/InterviewDetail'

// The LiveKit client is far larger than the rest of the app, and only the call
// page needs it, so it stays out of the initial bundle.
const CallPage = lazy(() =>
  import('./pages/CallPage').then((module) => ({ default: module.CallPage })),
)

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link className="brand" to="/">
          Interview Agent
        </Link>
        <nav>
          <Link to="/">Candidates</Link>
        </nav>
      </header>
      <main>
        <Suspense fallback={<Loading label="Loading…" />}>
          <Routes>
            <Route path="/" element={<CandidateList />} />
            <Route path="/candidates/:candidateId" element={<CandidateDetail />} />
            <Route path="/interviews/:interviewId" element={<InterviewDetail />} />
            <Route path="/interviews/:interviewId/call" element={<CallPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
