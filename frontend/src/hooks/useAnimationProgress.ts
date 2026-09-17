import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

function subscribeReducedMotion(onChange: () => void) {
  const query = window.matchMedia?.(REDUCED_MOTION)
  query?.addEventListener('change', onChange)
  return () => query?.removeEventListener('change', onChange)
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia?.(REDUCED_MOTION).matches ?? false,
    () => false,
  )
}

/**
 * Progress from 0 to 1 over `durationMs`, restarted whenever `runKey` changes.
 *
 * `finish` jumps to the end (a tap on the animation), `replay` starts it again. With reduced motion,
 * or a zero duration, it is at the end from the first render.
 */
export function useAnimationProgress(durationMs: number, runKey: string) {
  const reduced = usePrefersReducedMotion()
  const instant = reduced || durationMs <= 0
  const [run, setRun] = useState({ key: runKey, replays: 0, finished: false })
  const [progress, setProgress] = useState(instant ? 1 : 0)

  // A new key is a new run: reset during render rather than after a frame at the old progress.
  if (run.key !== runKey) {
    setRun({ key: runKey, replays: run.replays, finished: false })
    setProgress(instant ? 1 : 0)
  }

  const finished = instant || run.finished

  useEffect(() => {
    if (finished) return
    let frame = 0
    let startedAt: number | null = null
    const tick = (now: number) => {
      startedAt ??= now
      const p = Math.min(1, (now - startedAt) / durationMs)
      setProgress(p)
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [finished, durationMs, run.key, run.replays])

  const finish = useCallback(() => setRun((r) => ({ ...r, finished: true })), [])
  const replay = useCallback(() => {
    setProgress(0)
    setRun((r) => ({ ...r, replays: r.replays + 1, finished: false }))
  }, [])

  const value = finished ? 1 : progress
  return { progress: value, done: value >= 1, finish, replay }
}
