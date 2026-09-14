import type { Leg, Route, Stop, Waypoint } from '../domain/types'
import type { Translate } from '../i18n'

export function stopById(route: Route, stopId: string): Stop {
  const stop = route.stops.find((s) => s.id === stopId)
  if (!stop) throw new Error(`Unknown stop ${stopId}`)
  return stop
}

export function waypointById(route: Route, waypointId: string): Waypoint {
  const waypoint = route.waypoints.find((w) => w.id === waypointId)
  if (!waypoint) throw new Error(`Unknown waypoint ${waypointId}`)
  return waypoint
}

export function stopWaypoint(route: Route, stopId: string): Waypoint {
  return waypointById(route, stopById(route, stopId).waypointId)
}

/** Short timeline label: official place names stay untranslated. */
export function stopLabel(stop: Stop, t: Translate): string {
  return 'place' in stop.label ? stop.label.place : t(stop.label.key)
}

export function routeName(route: Route): string {
  return `${route.fromName} → ${route.toName}`
}

/** "Moraine → Hohtürli → Hütte" for consecutive legs. */
export function legsRange(route: Route, legs: Leg[], t: Translate): string {
  if (legs.length === 0) return ''
  const ids = [legs[0].fromStop, ...legs.map((l) => l.toStop)]
  return ids.map((id) => stopLabel(stopById(route, id), t)).join(' → ')
}
