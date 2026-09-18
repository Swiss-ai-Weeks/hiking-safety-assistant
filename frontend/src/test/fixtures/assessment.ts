import type {
  Alternative,
  Forecast,
  GapKind,
  HazardDef,
  NotEvaluated,
  Severity,
  SeverityInterval,
  StopConditions,
} from '../../domain/types'
import { oeschinenRoute } from './route-oeschinensee'

export const forecast: Forecast = {
  model: 'ICON-CH1',
  issuedAt: 6 * 60 + 40,
  unavailableSince: 5 * 60 + 10,
  checkedAt: 8 * 60 + 12,
  staleHours: 7,
}

const span = (from: number, to: number, severity: Severity): SeverityInterval => ({ from, to, severity })

/** Moderate from the 10:30 build-up, high at the col and hut from 11:00 to 14:00. */
const gustsOnRidge = [span(10 * 60 + 30, 11 * 60, 'mod'), span(11 * 60, 14 * 60, 'high')]

export const hazards: HazardDef[] = [
  {
    id: 'gusts-hohturli',
    kind: 'gusts',
    window: { from: 11 * 60, to: 14 * 60 },
    stops: { moraine: [span(10 * 60 + 30, 14 * 60, 'mod')], hohturli: gustsOnRidge, hutte: gustsOnRidge },
    place: 'Hohtürli',
    hasLiftsIf: true,
    facts: { gustKmh: 60, thresholdKmh: 40, elevationM: 2778 },
    provenance: 'Rule WIND-EXP-02 v3 · SAC guidance · ICON-CH1 06:40',
  },
  {
    id: 'showers-descent',
    kind: 'showers',
    window: { from: 13 * 60, to: 18 * 60 },
    stops: { descent: [span(13 * 60, 18 * 60, 'mod')] },
    hasLiftsIf: false,
    facts: { precipMm: 1.2, thresholdMm: 0.5, freezingLevelM: 2900 },
    provenance: 'Rule PRECIP-DESC-01 v2 · ICON-CH1 06:40',
  },
]

const GUST_KMH: Record<Severity, number> = { none: 25, mod: 40, high: 55 }

/** Same as `_conditions` in `backend/tests/authored.py`: the authored gust figure per stretch of the day, and −2 °C. */
export function conditionsFor(list: HazardDef[]): Record<string, StopConditions[]> {
  const gusts = list.find((h) => h.kind === 'gusts')
  const conditions: Record<string, StopConditions[]> = {}
  for (const stop of oeschinenRoute.stops) {
    const rows: StopConditions[] = []
    let cursor = 0
    for (const interval of [...(gusts?.stops[stop.id] ?? []), span(24 * 60, 24 * 60, 'none')]) {
      if (interval.from > cursor) rows.push({ from: cursor, to: interval.from, gustKmh: GUST_KMH.none, feelsLikeC: -2 })
      if (interval.to > interval.from) {
        rows.push({ from: interval.from, to: interval.to, gustKmh: GUST_KMH[interval.severity], feelsLikeC: -2 })
      }
      cursor = Math.max(cursor, interval.to)
    }
    conditions[stop.id] = rows
  }
  return conditions
}

export const gaps: GapKind[] = ['warnings', 'snowline', 'pace']

export const alternatives: Alternative[] = [
  { id: 'start-earlier', kind: 'startEarlier', start: 6 * 60 + 30, dependsOn: 'gusts-hohturli' },
  { id: 'turn-at-ober', kind: 'altRoute', duration: '4 h 10', stopId: 'ober', place: 'Oberbärgli', grade: 'T2' },
]

/** Used by the "partially assessed" scenario: no gust data above 2 600 m. */
export const partialNotEvaluated: NotEvaluated[] = [{ legIds: ['moraine-hohturli', 'hohturli-hutte'] }]
