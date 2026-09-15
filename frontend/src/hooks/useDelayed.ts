import { useEffect, useState } from 'react'

/** Delay before hazards and alternatives "stream" in after the structured block. */
export const STREAM_DELAY_MS = 900

/** Becomes true after `ms`. Used to stream secondary blocks in after the structured ones. */
export function useDelayed(ms: number): boolean {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const id = setTimeout(() => setReady(true), ms)
    return () => clearTimeout(id)
  }, [ms])
  return ready
}
