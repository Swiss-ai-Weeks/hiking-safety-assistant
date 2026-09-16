import { paceFactor } from './timing'
import type { LatLng, Minutes, PaceAnswer, Route } from './types'

/**
 * Field mode from a real position: where on the route the hiker is, and what that leaves.
 *
 * The route is walked as its timeline — out and back — so the track is built stop by stop, not
 * from the geometry alone: the way down covers the same ground as the way up, and progress along
 * the timeline is what tells the two apart. Snapping only looks forward from the last progress
 * (less a small tolerance for GPS jitter), so standing on the moraine in the afternoon reads as the
 * descent, not the climb.
 */

const EARTH_RADIUS_M = 6_371_000
/** How far behind the last progress a fix may snap: GPS wanders, hikers step back. */
export const BACK_TOLERANCE_M = 150
/** Beyond this from the line, a fix is off route and does not move progress. */
export const OFF_ROUTE_M = 150

interface TrackPoint {
  latLng: LatLng
  elevationM: number
  /** Metres along the whole timeline. */
  alongM: number
}

/** One stop-to-stop stretch of the timeline: from stop `index - 1` to stop `index`. */
export interface Section {
  index: number
  points: TrackPoint[]
  startM: number
  lengthM: number
}

export interface Track {
  sections: Section[]
  lengthM: number
}

export interface Snap {
  progressM: number
  /** Distance from the fix to the line. */
  offRouteM: number
  /** Stop index the hiker is walking towards. */
  sectionIndex: number
  /** 0 at the previous stop, 1 at the next. */
  fraction: number
}

/** Local planar metres around `origin`: plenty at the scale of a hike. */
function toXY([lat, lng]: LatLng, originLat: number): [number, number] {
  const rad = Math.PI / 180
  return [lng * rad * EARTH_RADIUS_M * Math.cos(originLat * rad), lat * rad * EARTH_RADIUS_M]
}

export function distanceM(a: LatLng, b: LatLng): number {
  const [ax, ay] = toXY(a, a[0])
  const [bx, by] = toXY(b, a[0])
  return Math.hypot(bx - ax, by - ay)
}

/** Each waypoint's index into `route.geometry`, from the legs that start or end there. */
function geometryIndexByWaypoint(route: Route): Map<string, number> {
  const byStop = new Map(route.stops.map((stop) => [stop.id, stop.waypointId]))
  const index = new Map<string, number>()
  for (const leg of route.legs) {
    if (leg.fromIndex === undefined || leg.toIndex === undefined) continue
    const from = byStop.get(leg.fromStop)
    const to = byStop.get(leg.toStop)
    if (from !== undefined && !index.has(from)) index.set(from, leg.fromIndex)
    if (to !== undefined && !index.has(to)) index.set(to, leg.toIndex)
  }
  return index
}

/** The timeline as a line: the real geometry where the route has it, chords between stops where not. */
export function trackOf(route: Route): Track {
  const waypoints = new Map(route.waypoints.map((w) => [w.id, w]))
  const geometryIndex = route.geometry ? geometryIndexByWaypoint(route) : new Map<string, number>()
  const sections: Section[] = []
  let alongM = 0

  for (let i = 1; i < route.stops.length; i++) {
    const a = waypoints.get(route.stops[i - 1].waypointId)
    const b = waypoints.get(route.stops[i].waypointId)
    if (!a || !b) continue
    const from = geometryIndex.get(a.id)
    const to = geometryIndex.get(b.id)

    let raw: { latLng: LatLng; elevationM: number }[]
    if (route.geometry && from !== undefined && to !== undefined) {
      const [low, high] = from <= to ? [from, to] : [to, from]
      raw = route.geometry.slice(low, high + 1).map((latLng, k) => ({
        latLng,
        elevationM: route.elevations?.[low + k] ?? a.elevationM,
      }))
      if (from > to) raw.reverse()
    } else {
      raw = [
        { latLng: a.latLng, elevationM: a.elevationM },
        { latLng: b.latLng, elevationM: b.elevationM },
      ]
    }

    const startM = alongM
    const points: TrackPoint[] = raw.map((point, k) => {
      if (k > 0) alongM += distanceM(raw[k - 1].latLng, point.latLng)
      return { ...point, alongM }
    })
    sections.push({ index: i, points, startM, lengthM: alongM - startM })
  }
  return { sections, lengthM: alongM }
}

/** The nearest point on the track at or after `minProgressM` (less the jitter tolerance). */
export function snapToTrack(track: Track, position: LatLng, minProgressM = 0): Snap | null {
  let best: Snap | null = null
  const [px, py] = toXY(position, position[0])

  for (const section of track.sections) {
    const { points } = section
    for (let k = 1; k < points.length; k++) {
      const a = points[k - 1]
      const b = points[k]
      if (b.alongM < minProgressM - BACK_TOLERANCE_M) continue
      const [ax, ay] = toXY(a.latLng, position[0])
      const [bx, by] = toXY(b.latLng, position[0])
      const dx = bx - ax
      const dy = by - ay
      const lengthSq = dx * dx + dy * dy
      const u = lengthSq === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq))
      const offRouteM = Math.hypot(ax + u * dx - px, ay + u * dy - py)
      // Strictly nearer only: where the way down retraces the way up, the earlier pass wins.
      if (best === null || offRouteM < best.offRouteM - 0.5) {
        const progressM = a.alongM + u * (b.alongM - a.alongM)
        best = {
          progressM,
          offRouteM,
          sectionIndex: section.index,
          fraction: section.lengthM === 0 ? 1 : (progressM - section.startM) / section.lengthM,
        }
      }
    }
  }
  return best
}

/** Where the plan says the hiker is at `now`, for when there is no position to go on. */
export function plannedSnap(track: Track, arrivals: Record<string, Minutes>, route: Route, now: Minutes): Snap {
  for (const section of track.sections) {
    const previous = route.stops[section.index - 1]
    const leaveAt = arrivals[previous.id] + (previous.breakMinutes ?? 0)
    const arriveAt = arrivals[route.stops[section.index].id]
    if (now < arriveAt) {
      const fraction = arriveAt === leaveAt ? 1 : Math.max(0, (now - leaveAt) / (arriveAt - leaveAt))
      return { progressM: section.startM + fraction * section.lengthM, offRouteM: 0, sectionIndex: section.index, fraction }
    }
  }
  const last = track.sections[track.sections.length - 1]
  return { progressM: track.lengthM, offRouteM: 0, sectionIndex: last?.index ?? 0, fraction: 1 }
}

export interface FieldProgress {
  /** The stop being walked towards: the crux until it is passed, then the end of the hike. */
  targetStopId: string
  passedCrux: boolean
  /** Moving time plus breaks from here to the target, at the hiker's pace. */
  remainingMinutes: Minutes
  eta: Minutes
  remainingKm: number
  remainingAscentM: number
}

function elevationAt(track: Track, alongM: number): number | null {
  for (const section of track.sections) {
    const { points } = section
    for (let k = 1; k < points.length; k++) {
      const a = points[k - 1]
      const b = points[k]
      if (alongM >= a.alongM && alongM <= b.alongM) {
        const u = b.alongM === a.alongM ? 1 : (alongM - a.alongM) / (b.alongM - a.alongM)
        return a.elevationM + u * (b.elevationM - a.elevationM)
      }
    }
  }
  return null
}

function ascentBetween(track: Track, fromM: number, toM: number): number {
  let ascent = 0
  let previous = elevationAt(track, fromM)
  for (const section of track.sections) {
    for (const point of section.points) {
      if (point.alongM <= fromM || point.alongM > toM) continue
      if (previous !== null && point.elevationM > previous) ascent += point.elevationM - previous
      previous = point.elevationM
    }
  }
  return ascent
}

export function fieldProgress(
  route: Route,
  track: Track,
  snap: Snap,
  pace: PaceAnswer | null,
  now: Minutes,
): FieldProgress {
  const factor = paceFactor(pace)
  const cruxIndex = route.stops.findIndex((stop) => stop.id === route.cruxStopId)
  const passedCrux = cruxIndex >= 0 && snap.sectionIndex > cruxIndex
  const targetIndex = passedCrux || cruxIndex < 0 ? route.stops.length - 1 : cruxIndex

  let remainingMinutes = 0
  if (snap.sectionIndex <= targetIndex) {
    remainingMinutes = (1 - snap.fraction) * route.stops[snap.sectionIndex].legMinutes * factor
    for (let i = snap.sectionIndex + 1; i <= targetIndex; i++) {
      remainingMinutes += (route.stops[i - 1].breakMinutes ?? 0) + route.stops[i].legMinutes * factor
    }
  }

  const targetSection = track.sections.find((section) => section.index === targetIndex)
  const targetM = targetSection ? targetSection.startM + targetSection.lengthM : track.lengthM
  const remainingM = Math.max(0, targetM - snap.progressM)

  return {
    targetStopId: route.stops[targetIndex].id,
    passedCrux,
    remainingMinutes,
    eta: now + remainingMinutes,
    remainingKm: remainingM / 1000,
    remainingAscentM: ascentBetween(track, snap.progressM, targetM),
  }
}
