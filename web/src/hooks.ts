import { useCallback, useEffect, useRef, useState } from 'react'
import { describeError } from './api'

interface Fetched<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

export function useFetch<T>(load: () => Promise<T>): Fetched<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  const latest = useRef(load)
  useEffect(() => {
    latest.current = load
  })

  useEffect(() => {
    let cancelled = false
    latest
      .current()
      .then((value) => {
        if (cancelled) return
        setData(value)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setError(describeError(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tick])

  const reload = useCallback(() => {
    setLoading(true)
    setTick((value) => value + 1)
  }, [])
  return { data, error, loading, reload }
}

function useLatest<A extends unknown[]>(fn: (...args: A) => void) {
  const latest = useRef(fn)
  useEffect(() => {
    latest.current = fn
  })
  return latest
}

export function useRefreshShortcut(reload: () => void): void {
  const latest = useLatest(reload)

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== 'r') return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (
        target &&
        (target.isContentEditable ||
          ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
      ) {
        return
      }
      event.preventDefault()
      latest.current()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [latest])
}

export function usePolling(
  enabled: boolean,
  reload: () => void,
  intervalMs = 3000,
): void {
  const latest = useLatest(reload)

  useEffect(() => {
    if (!enabled) return
    const handle = window.setInterval(() => latest.current(), intervalMs)
    return () => window.clearInterval(handle)
  }, [enabled, intervalMs, latest])
}
