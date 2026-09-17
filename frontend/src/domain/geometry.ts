import type { Track } from './field'
import type { LatLng } from './types'

/**
 * Reading the walked track (see `trackOf`) by distance, for the briefing's animations: the walker's
 * position, the line drawn so far and the elevation profile.
 */

export interface TrackPosition {
  latLng: LatLng
  elevationM: number
}

/** The point `alongM` metres into the track, clamped to its ends. */
export function pointAlong(track: Track, alongM: number): TrackPosition | null {
  const points = track.sections.flatMap((section) => section.points)
  if (points.length === 0) return null
  if (alongM <= points[0].alongM) return { latLng: points[0].latLng, elevationM: points[0].elevationM }
  for (let k = 1; k < points.length; k++) {
    const a = points[k - 1]
    const b = points[k]
    if (alongM <= b.alongM) {
      const u = b.alongM === a.alongM ? 1 : (alongM - a.alongM) / (b.alongM - a.alongM)
      return {
        latLng: [a.latLng[0] + u * (b.latLng[0] - a.latLng[0]), a.latLng[1] + u * (b.latLng[1] - a.latLng[1])],
        elevationM: a.elevationM + u * (b.elevationM - a.elevationM),
      }
    }
  }
  const end = points[points.length - 1]
  return { latLng: end.latLng, elevationM: end.elevationM }
}

/** The line from the start of the track up to `alongM`, ending exactly there. */
export function pathUpTo(track: Track, alongM: number): LatLng[] {
  const path: LatLng[] = []
  for (const section of track.sections) {
    for (const point of section.points) {
      if (point.alongM > alongM) {
        const end = pointAlong(track, alongM)
        if (end) path.push(end.latLng)
        return path
      }
      path.push(point.latLng)
    }
  }
  return path
}

/** Where each stop sits along the track, by stop index. The first stop is at 0. */
export function stopAlongM(track: Track, stopCount: number): number[] {
  const along = new Array<number>(stopCount).fill(0)
  for (const section of track.sections) along[section.index] = section.startM + section.lengthM
  // A stop with no section of its own (missing waypoint) sits where the previous one did.
  for (let i = 1; i < stopCount; i++) if (along[i] < along[i - 1]) along[i] = along[i - 1]
  return along
}

export interface ProfilePoint {
  alongM: number
  elevationM: number
}

/** `samples` evenly spaced elevations along the track, for drawing a profile. */
export function profileOf(track: Track, samples = 80): ProfilePoint[] {
  if (track.lengthM === 0) return []
  return Array.from({ length: samples }, (_, i) => {
    const alongM = (track.lengthM * i) / (samples - 1)
    return { alongM, elevationM: pointAlong(track, alongM)?.elevationM ?? 0 }
  })
}
