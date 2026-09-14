import type {
  AssessmentData,
  HazardDef,
  Leg,
  Minutes,
  Route,
  Severity,
  StopSeverity,
} from './types'

const RANK: Record<Severity, number> = { none: 0, mod: 1, high: 2 }

export function maxSeverity(list: Severity[]): Severity {
  return list.reduce<Severity>((acc, s) => (RANK[s] > RANK[acc] ? s : acc), 'none')
}

/** Severity of one hazard at one stop, for the hour the hiker is there. */
export function hazardSeverityAt(hazard: HazardDef, stopId: string, minute: Minutes): Severity {
  const atWindow = hazard.stops[stopId]
  if (!atWindow) return 'none'
  if (minute >= hazard.window.from && minute <= hazard.window.to) return atWindow
  if (hazard.buildUpFrom !== undefined && minute >= hazard.buildUpFrom && minute < hazard.window.from) {
    return 'mod'
  }
  return 'none'
}

export interface FlaggedHazard {
  hazard: HazardDef
  severity: Severity
}

export interface Evaluation {
  stopSeverity: Record<string, StopSeverity>
  legSeverity: Record<string, StopSeverity>
  /** Hazard responsible for a leg's severity, if any. */
  legCause: Record<string, HazardDef | null>
  flagged: FlaggedHazard[]
  notEvaluatedLegs: Leg[]
}

export function evaluate(route: Route, arrivals: Record<string, Minutes>, data: AssessmentData): Evaluation {
  const notEvaluatedLegs = route.legs.filter((leg) =>
    data.notEvaluated.some((n) => n.legIds.includes(leg.id)),
  )
  const unknownStops = new Set(
    notEvaluatedLegs.flatMap((leg) => [leg.fromStop, leg.toStop]).filter((id) => id !== route.stops[0].id),
  )

  const known = (stopId: string): Severity =>
    maxSeverity(data.hazards.map((h) => hazardSeverityAt(h, stopId, arrivals[stopId])))

  const stopSeverity: Record<string, StopSeverity> = {}
  for (const stop of route.stops) {
    stopSeverity[stop.id] = unknownStops.has(stop.id) ? 'unknown' : known(stop.id)
  }

  const legSeverity: Record<string, StopSeverity> = {}
  const legCause: Record<string, HazardDef | null> = {}
  for (const leg of route.legs) {
    if (notEvaluatedLegs.includes(leg)) {
      legSeverity[leg.id] = 'unknown'
      legCause[leg.id] = null
      continue
    }
    let best: Severity = 'none'
    let cause: HazardDef | null = null
    for (const hazard of data.hazards) {
      for (const stopId of leg.stopIds) {
        const s = hazardSeverityAt(hazard, stopId, arrivals[stopId])
        if (RANK[s] > RANK[best]) {
          best = s
          cause = hazard
        }
      }
    }
    legSeverity[leg.id] = best
    legCause[leg.id] = cause
  }

  const flagged = data.hazards
    .map((hazard) => ({
      hazard,
      severity: maxSeverity(
        Object.keys(hazard.stops).map((stopId) => hazardSeverityAt(hazard, stopId, arrivals[stopId])),
      ),
    }))
    .filter((f) => f.severity !== 'none')
    .sort((a, b) => RANK[b.severity] - RANK[a.severity] || a.hazard.window.from - b.hazard.window.from)

  return { stopSeverity, legSeverity, legCause, flagged, notEvaluatedLegs }
}

/**
 * The opening run of stops with nothing flagged, for the sentence
 * "Nothing flagged on X → Y given data as of HH:MM". Null when fewer than two.
 */
export function nothingFlaggedRange(
  route: Route,
  stopSeverity: Record<string, StopSeverity>,
): { from: string; to: string } | 'all' | null {
  if (route.stops.every((s) => stopSeverity[s.id] === 'none')) return 'all'
  let end = -1
  for (let i = 0; i < route.stops.length; i++) {
    if (stopSeverity[route.stops[i].id] !== 'none') break
    end = i
  }
  if (end < 1) return null
  return { from: route.stops[0].id, to: route.stops[end].id }
}

/** Forecast gust speed at a stop for the crux card. */
export function gustAt(
  hazards: HazardDef[],
  stopId: string,
  minute: Minutes,
): { kmh: number; severity: Severity } {
  const gusts = hazards.find((h) => h.kind === 'gusts')
  const severity = gusts ? hazardSeverityAt(gusts, stopId, minute) : 'none'
  const kmh = severity === 'high' ? 55 : severity === 'mod' ? 40 : 25
  return { kmh, severity }
}
