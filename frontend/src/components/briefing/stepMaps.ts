import { conditionsAt, gustAt } from '../../domain/assessment'
import { pathUpTo, pointAlong } from '../../domain/geometry'
import { formatArrival, formatClock } from '../../domain/timing'
import type { PaceAnswer, StopConditions } from '../../domain/types'
import { formatInt, formatTemp } from '../../lib/format'
import { HAZARD_ORDER, legPaintAt, type BriefingModel } from './model'
import type { MapPin } from './RouteMap'
import type { MapContext, StepMap } from './steps/types'

/**
 * What each step shows on the shared map, as pure functions of the step's animation progress. The
 * panels live in `steps/`; the map stays mounted across steps, so only its inputs change.
 */

export const ROUTE_STEP_MS = 3200
export const TIME_STEP_MS = 3600
export const WEATHER_STEP_MS = 3600
const CHECK_MS = 420
export const HAZARD_STEP_MS = CHECK_MS * (HAZARD_ORDER.length + 1)

export const PACE_OPTIONS: PaceAnswer[] = ['under5', '5to6', 'over7']

/** The walker's clock at `progress`, from the first step to the last. */
export function minuteAt(model: BriefingModel, progress: number) {
  return model.start + progress * (model.end - model.start)
}

/** How many of the hazard checks have resolved at `progress`. */
export function resolvedChecks(progress: number): number {
  return progress >= 1 ? HAZARD_ORDER.length : Math.min(HAZARD_ORDER.length, Math.floor(progress * (HAZARD_ORDER.length + 1)))
}

/** 1. The line draws itself out and back; the named points appear as the walker reaches them. */
export function routeStepMap({ model, progress, t }: MapContext): StepMap {
  const alongM = progress * model.track.lengthM
  const pins: MapPin[] = model.keyStops
    .filter((key) => progress >= 1 || model.stopAlong[key.index] <= alongM + 1)
    .map((key) => ({
      key: `route-${key.stop.waypointId}`,
      latLng: key.latLng,
      below: key.role === 'crux',
      text:
        key.role === 'crux'
          ? `${key.name} · ${formatInt(key.elevationM)} m`
          : key.role === 'bailout'
            ? `${key.name} · ${t('map.bailout')}`
            : key.name,
      variant: key.role === 'crux' ? 'crux' : key.role === 'bailout' ? 'turn' : '',
    }))
  return {
    legPaint: 'plain',
    drawnPath: progress < 1 ? pathUpTo(model.track, alongM) : null,
    walker: progress < 1 ? (pointAlong(model.track, alongM)?.latLng ?? null) : null,
    pins,
  }
}

/** 2. The walker replays against the clock; each named point takes the times you pass it. */
export function timeStepMap({ view, model, progress, t, turnaround }: MapContext): StepMap {
  const minute = minuteAt(model, progress)
  const pins: MapPin[] = model.keyStops.map((key) => {
    const times = view.route.stops
      .filter((stop) => stop.waypointId === key.stop.waypointId && view.arrivals[stop.id] <= minute + 0.5)
      .map((stop) => formatArrival(view.arrivals[stop.id]))
    const suffix = key.role === 'crux' && progress >= 1 ? ` · ${t('map.turnBy', { time: formatClock(turnaround) })}` : ''
    return {
      key: `time-${key.stop.waypointId}`,
      latLng: key.latLng,
      below: key.role === 'crux',
      text: times.length ? `${key.name} · ${times.join(' · ')}${suffix}` : key.name,
      variant: key.role === 'crux' ? 'crux' : '',
    }
  })
  return { legPaint: 'plain', walker: progress < 1 ? model.walkerAt(minute).latLng : null, pins }
}

function weatherText(conditions: StopConditions | null, noData: string): string {
  if (!conditions) return noData
  const parts: string[] = []
  if (conditions.gustKmh !== undefined) parts.push(`${formatInt(conditions.gustKmh)} km/h`)
  if (conditions.feelsLikeC !== undefined) parts.push(formatTemp(conditions.feelsLikeC))
  return parts.join(' · ') || noData
}

/** 3. Each named point shows the weather for the hour you reach it, as the walker gets there. */
export function weatherStepMap({ view, model, progress, t }: MapContext): StepMap {
  const minute = minuteAt(model, progress)
  const assessable = view.data.outcome !== 'not_assessable'
  const pins: MapPin[] = model.keyStops.map((key) => {
    const arrival = view.arrivals[key.stop.id]
    const reached = assessable && arrival <= minute + 0.5
    const unknown = view.evaluation.stopSeverity[key.stop.id] === 'unknown'
    const gust = reached && !unknown ? gustAt(view.data, key.stop.id, arrival) : null
    const conditions = unknown ? null : conditionsAt(view.data, key.stop.id, arrival)
    return {
      key: `weather-${key.stop.waypointId}`,
      latLng: key.latLng,
      below: key.role === 'crux',
      text: reached ? `${key.name} ${formatArrival(arrival)} · ${weatherText(conditions, t('brief.noData'))}` : key.name,
      variant: gust && gust.severity !== 'none' ? 'warn' : key.role === 'crux' ? 'crux' : '',
    }
  })
  return {
    legPaint: 'plain',
    walker: assessable && progress < 1 ? model.walkerAt(minute).latLng : null,
    pins,
  }
}

/** 4. Legs take their colour as the check behind it resolves. */
export function hazardStepMap({ view, model, progress }: MapContext): StepMap {
  const done = resolvedChecks(progress) >= HAZARD_ORDER.length
  const pins: MapPin[] = model.keyStops.map((key) => {
    const severity = view.evaluation.stopSeverity[key.stop.id]
    return {
      key: `hazard-${key.stop.waypointId}`,
      latLng: key.latLng,
      below: key.role === 'crux',
      text: key.name,
      variant: done && (severity === 'mod' || severity === 'high') ? 'warn' : key.role === 'crux' ? 'crux' : '',
    }
  })
  return { legPaint: legPaintAt(view, resolvedChecks(progress)), pins }
}

/** 5. The finished picture: legs in their colours, and the places the rule names. */
export function planStepMap({ view, model, t, turnaround }: MapContext): StepMap {
  const pins: MapPin[] = model.keyStops.map((key) => ({
    key: `plan-${key.stop.waypointId}`,
    latLng: key.latLng,
    below: key.role === 'crux',
    text:
      key.role === 'crux'
        ? `${key.name} · ${t('map.turnBy', { time: formatClock(turnaround) })}`
        : key.role === 'bailout'
          ? `${key.name} · ${t('map.bailout')}`
          : key.role === 'start'
            ? `${key.name} · ${formatClock(view.start)}`
            : key.name,
    variant: key.role === 'crux' ? 'crux' : key.role === 'bailout' ? 'turn' : '',
  }))
  return { legPaint: view.evaluation.legSeverity, pins }
}
