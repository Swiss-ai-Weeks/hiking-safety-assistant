import type { Alternative, Forecast, GapKind, HazardDef, NotEvaluated } from '../../domain/types'

export const forecast: Forecast = {
  model: 'ICON-CH1',
  issuedAt: 6 * 60 + 40,
  unavailableSince: 5 * 60 + 10,
  checkedAt: 8 * 60 + 12,
  staleHours: 7,
  feelsLikeC: -2,
}

export const hazards: HazardDef[] = [
  {
    id: 'gusts-hohturli',
    kind: 'gusts',
    window: { from: 11 * 60, to: 14 * 60 },
    buildUpFrom: 10 * 60 + 30,
    stops: { moraine: 'mod', hohturli: 'high', hutte: 'high' },
    place: 'Hohtürli',
    hasLiftsIf: true,
    provenance: 'Rule WIND-EXP-02 v3 · SAC guidance · ICON-CH1 06:40',
  },
  {
    id: 'showers-descent',
    kind: 'showers',
    window: { from: 13 * 60, to: 18 * 60 },
    stops: { descent: 'mod' },
    hasLiftsIf: false,
    provenance: 'Rule PRECIP-DESC-01 v2 · ICON-CH1 06:40',
  },
]

export const gaps: GapKind[] = ['warnings', 'snowline', 'pace']

export const alternatives: Alternative[] = [
  { id: 'start-earlier', kind: 'startEarlier', start: 6 * 60 + 30, dependsOn: 'gusts-hohturli' },
  { id: 'high-loop', kind: 'altRoute', duration: '4 h 10' },
]

/** Used by the "partially assessed" scenario: no gust data above 2 600 m. */
export const partialNotEvaluated: NotEvaluated[] = [{ legIds: ['moraine-hohturli', 'hohturli-hutte'] }]
