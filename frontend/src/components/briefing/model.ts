import { useMemo } from 'react'
import { plannedSnap, trackOf } from '../../domain/field'
import { pointAlong, profileOf, stopAlongM } from '../../domain/geometry'
import type { HazardKind, LatLng, Minutes, Stop, StopSeverity } from '../../domain/types'
import type { AssessmentView } from '../../hooks/useAssessmentView'
import { waypointById } from '../../lib/route'
import type { LegPaint } from './RouteMap'

/** The checks the hazard engine runs, in the order the briefing resolves them. */
export const HAZARD_ORDER: HazardKind[] = ['gusts', 'showers', 'thunder', 'cold', 'snow', 'visibility', 'daylight']

export type KeyRole = 'start' | 'crux' | 'bailout' | 'destination'

export interface KeyStop {
  role: KeyRole
  stop: Stop
  index: number
  name: string
  elevationM: number
  latLng: LatLng
}

/** Everything the steps share: the walked track, where each stop sits on it, and the points worth naming. */
export function useBriefingModel(view: Pick<AssessmentView, 'route' | 'arrivals' | 'start'>) {
  const { route, arrivals, start } = view
  const track = useMemo(() => trackOf(route), [route])
  const stopAlong = useMemo(() => stopAlongM(track, route.stops.length), [track, route.stops.length])
  const profile = useMemo(() => profileOf(track), [track])

  const keyStops = useMemo(() => {
    const cruxIndex = route.stops.findIndex((s) => s.id === route.cruxStopId)
    // A computed route names the bail-out stop; the demo route only gives a name to match.
    const bailoutIndex = route.bailoutStopId
      ? route.stops.findIndex((s) => s.id === route.bailoutStopId)
      : route.stops.findIndex((s) => waypointById(route, s.waypointId).name === route.bailoutName)
    // The far end of an out-and-back: where the break is taken, else the middle.
    const breakIndex = route.stops.findIndex((s) => s.breakMinutes)
    const destinationIndex = breakIndex >= 0 ? breakIndex : Math.floor((route.stops.length - 1) / 2)

    const candidates: [KeyRole, number][] = [
      ['start', 0],
      ['crux', cruxIndex],
      ['bailout', bailoutIndex],
      ['destination', destinationIndex],
    ]
    const seen = new Set<string>()
    const result: KeyStop[] = []
    for (const [role, index] of candidates) {
      const stop = route.stops[index]
      if (!stop || seen.has(stop.waypointId)) continue
      seen.add(stop.waypointId)
      const waypoint = waypointById(route, stop.waypointId)
      result.push({ role, stop, index, name: waypoint.name, elevationM: waypoint.elevationM, latLng: waypoint.latLng })
    }
    return result
  }, [route])

  const end = arrivals[route.stops[route.stops.length - 1].id]

  return useMemo(
    () => ({
      track,
      stopAlong,
      profile,
      keyStops,
      start,
      end,
      /** Where the plan puts the hiker at `minute`, as a map position and metres along. */
      walkerAt: (minute: Minutes) => {
        const alongM = plannedSnap(track, arrivals, route, minute).progressM
        return { alongM, latLng: pointAlong(track, alongM)?.latLng ?? null }
      },
    }),
    [track, stopAlong, profile, keyStops, start, end, arrivals, route],
  )
}

export type BriefingModel = ReturnType<typeof useBriefingModel>

/**
 * How far the hazard check has got, as legs painted on the map: a leg keeps its ink until the check
 * responsible for its colour has resolved, and legs with nothing flagged settle last.
 */
export function legPaintAt(view: AssessmentView, resolvedChecks: number): Record<string, LegPaint> {
  const { evaluation, route } = view
  const paint: Record<string, LegPaint> = {}
  for (const leg of route.legs) {
    const severity: StopSeverity = evaluation.legSeverity[leg.id]
    const cause = evaluation.legCause[leg.id]
    const resolvesAt = cause ? HAZARD_ORDER.indexOf(cause.kind) + 1 : HAZARD_ORDER.length
    paint[leg.id] = resolvedChecks >= resolvesAt ? severity : 'plain'
  }
  return paint
}

/** Ease-out for numbers counting up. */
export function easeOut(p: number): number {
  return 1 - (1 - p) ** 3
}
