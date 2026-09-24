import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Room, RoomEvent, Track } from 'livekit-client'
import { api, describeError } from '../api'
import { ErrorNote } from '../components/ui'

type Phase = 'connecting' | 'live' | 'ended' | 'error'

export function CallPage() {
  const { interviewId = '' } = useParams()
  const navigate = useNavigate()

  const [phase, setPhase] = useState<Phase>('connecting')
  const [error, setError] = useState<string | null>(null)
  const [muted, setMuted] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const roomRef = useRef<Room | null>(null)

  useEffect(() => {
    let cancelled = false
    let room: Room | null = null
    const playing: HTMLMediaElement[] = []

    async function connect() {
      try {
        const started = await api.startInterview(interviewId)
        if (cancelled) return

        room = new Room()
        roomRef.current = room
        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind !== Track.Kind.Audio) return
          const element = track.attach()
          playing.push(element)
          document.body.appendChild(element)
        })
        room.on(RoomEvent.Disconnected, () => {
          if (!cancelled) setPhase('ended')
        })

        await room.connect(started.livekit_url, started.token)
        if (cancelled) {
          await room.disconnect()
          return
        }
        await room.localParticipant.setMicrophoneEnabled(true)
        setPhase('live')
      } catch (cause) {
        if (cancelled) return
        setError(describeError(cause))
        setPhase('error')
      }
    }

    void connect()

    return () => {
      cancelled = true
      playing.forEach((element) => element.remove())
      void room?.disconnect()
    }
  }, [interviewId])

  async function hangUp() {
    setLeaving(true)
    await roomRef.current?.disconnect()
    await api.endInterview(interviewId).catch(() => undefined)
    navigate(`/interviews/${interviewId}`)
  }

  async function toggleMicrophone() {
    const room = roomRef.current
    if (!room) return
    const next = !muted
    setMuted(next)
    await room.localParticipant.setMicrophoneEnabled(!next)
  }

  return (
    <div className="stack">
      <div className="row">
        <h1>{phase === 'live' ? 'Interview in progress' : 'Interview'}</h1>
        <span className="spacer" />
        <span className="hint">Speak normally — the interviewer listens for turn ends.</span>
      </div>

      <section className="card">
        <div className="call-stage">
          <div className={['orb', phase === 'live' && 'orb--live'].filter(Boolean).join(' ')} />
          <div>
            <h2>
              {phase === 'connecting' && 'Connecting…'}
              {phase === 'live' && (muted ? 'Microphone muted' : 'Listening')}
              {phase === 'ended' && 'The call has ended'}
              {phase === 'error' && 'Could not join'}
            </h2>
            <p className="muted">
              {phase === 'live'
                ? 'The interviewer will ask one question at a time. It stops on its own when the budget runs out.'
                : null}
            </p>
          </div>

          <div className="row">
            {phase === 'live' && (
              <button className="button" type="button" onClick={toggleMicrophone}>
                {muted ? 'Unmute' : 'Mute'}
              </button>
            )}
            <button
              className="button button--danger"
              type="button"
              disabled={leaving || phase === 'error'}
              onClick={hangUp}
            >
              End and score
            </button>
          </div>
        </div>
      </section>

      {error && <ErrorNote message={error} />}
    </div>
  )
}
