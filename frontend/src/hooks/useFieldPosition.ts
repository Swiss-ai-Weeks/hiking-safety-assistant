import { useEffect, useRef, useState } from 'react'
import { OFF_ROUTE_M, snapToTrack, type Snap, type Track } from '../domain/field'
import type { LatLng } from '../domain/types'

/** A fix vaguer than this says nothing useful about which part of a trail you are on. */
const MAX_ACCURACY_M = 250

export type FieldPositionStatus = 'searching' | 'tracking' | 'offRoute' | 'denied' | 'unavailable'

export interface FieldPosition {
  status: FieldPositionStatus
  /** The last on-route position. Kept while off route, so progress is never lost to a detour. */
  snap: Snap | null
  /** The latest usable fix itself, on route or not: where the hiker actually is on the map. */
  fix?: LatLng
}

/**
 * Watches the device position and snaps it to `track`.
 *
 * Progress only moves forward (within the snap's jitter tolerance) and only on route, which is
 * what lets an out-and-back route tell the climb from the descent.
 */
export function useFieldPosition(track: Track, enabled: boolean): FieldPosition {
  const [position, setPosition] = useState<FieldPosition>(() => ({
    status: 'geolocation' in navigator ? 'searching' : 'unavailable',
    snap: null,
  }))
  const progressRef = useRef(0)

  useEffect(() => {
    progressRef.current = 0
    if (!enabled || !('geolocation' in navigator)) return

    const id = navigator.geolocation.watchPosition(
      ({ coords }) => {
        if (coords.accuracy > MAX_ACCURACY_M) return
        const fix: LatLng = [coords.latitude, coords.longitude]
        const snap = snapToTrack(track, fix, progressRef.current)
        if (snap === null) return
        if (snap.offRouteM > OFF_ROUTE_M) {
          setPosition((current) => ({ status: 'offRoute', snap: current.snap, fix }))
          return
        }
        progressRef.current = Math.max(progressRef.current, snap.progressM)
        setPosition({ status: 'tracking', snap, fix })
      },
      (error) => {
        setPosition((current) => ({
          status: error.code === error.PERMISSION_DENIED ? 'denied' : current.snap ? current.status : 'unavailable',
          snap: current.snap,
          fix: current.fix,
        }))
      },
      { enableHighAccuracy: true, maximumAge: 30_000, timeout: 60_000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [track, enabled])

  return position
}
