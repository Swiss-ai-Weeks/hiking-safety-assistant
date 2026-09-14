import { useEffect, useState } from 'react'

/** Becomes true after `ms`. Used to stream secondary blocks in after the structured ones. */
export function useDelayed(ms: number): boolean {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const id = setTimeout(() => setReady(true), ms)
    return () => clearTimeout(id)
  }, [ms])
  return ready
}
