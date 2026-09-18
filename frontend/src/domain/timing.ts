import type { Minutes, PaceAnswer, Route } from './types'

/**
 * Multipliers on the route's reference moving times. Until the hiker answers the
 * signpost question we assume a cautious pace.
 */
export const PACE_FACTORS: Record<PaceAnswer | 'cautious', number> = {
  cautious: 1.08,
  faster: 0.85,
  same: 1,
  slower: 1.25,
}

export function paceFactor(answer: PaceAnswer | null): number {
  return PACE_FACTORS[answer ?? 'cautious']
}

/** Arrival time at every stop, unrounded. */
export function computeArrivals(
  route: Route,
  start: Minutes,
  answer: PaceAnswer | null,
): Record<string, Minutes> {
  const factor = paceFactor(answer)
  const arrivals: Record<string, Minutes> = {}
  let t = start
  for (const stop of route.stops) {
    t += stop.legMinutes * factor
    arrivals[stop.id] = t
    t += stop.breakMinutes ?? 0
  }
  return arrivals
}

export function roundTo5(m: Minutes): Minutes {
  return Math.round(m / 5) * 5
}

export function formatClock(m: Minutes): string {
  const total = ((Math.round(m) % 1440) + 1440) % 1440
  const h = Math.floor(total / 60)
  const min = total % 60
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`
}

/** Planned arrivals are shown to the nearest five minutes. */
export function formatArrival(m: Minutes): string {
  return formatClock(roundTo5(m))
}

export function parseClock(value: string): Minutes | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim())
  if (!match) return null
  const h = Number(match[1])
  const min = Number(match[2])
  if (h > 23 || min > 59) return null
  return h * 60 + min
}

export function clockOf(date: Date): Minutes {
  return date.getHours() * 60 + date.getMinutes()
}

export type TurnaroundStatus = 'ahead' | 'behind'

export function turnaroundStatus(eta: Minutes, turnaround: Minutes): TurnaroundStatus {
  return eta <= turnaround ? 'ahead' : 'behind'
}
