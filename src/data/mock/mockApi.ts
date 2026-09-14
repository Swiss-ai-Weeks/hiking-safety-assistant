import type { AssessmentData, Scenario } from '../../domain/types'
import { alternatives, forecast, gaps, hazards, partialNotEvaluated } from './assessment'

const SCENARIOS: Scenario[] = ['assessed', 'partial', 'not_assessable', 'stale']

/** Delay before hazards and alternatives "stream" in after the structured block. */
export const STREAM_DELAY_MS = 900

/** `?outcome=` and `?stale=1` override the scenario chosen in settings. */
export function resolveScenario(fromSettings: Scenario, params: URLSearchParams): Scenario {
  if (params.get('stale') === '1') return 'stale'
  const outcome = params.get('outcome')
  return SCENARIOS.includes(outcome as Scenario) ? (outcome as Scenario) : fromSettings
}

export function getAssessmentData(scenario: Scenario): AssessmentData {
  switch (scenario) {
    case 'not_assessable':
      return { outcome: 'not_assessable', stale: false, forecast, hazards: [], gaps: [], alternatives: [], notEvaluated: [] }
    case 'partial':
      return {
        outcome: 'partial',
        stale: false,
        forecast,
        hazards: hazards.filter((h) => h.kind !== 'gusts'),
        gaps,
        alternatives: alternatives.filter((a) => a.kind !== 'startEarlier'),
        notEvaluated: partialNotEvaluated,
      }
    case 'stale':
    case 'assessed':
      return { outcome: 'assessed', stale: scenario === 'stale', forecast, hazards, gaps, alternatives, notEvaluated: [] }
  }
}

/** "Try again" on the not-assessable screen: the source is still down. */
export function retryForecast(now: Date = new Date()): Promise<{ available: false; checkedAt: number }> {
  return new Promise((resolve) =>
    setTimeout(() => resolve({ available: false, checkedAt: now.getHours() * 60 + now.getMinutes() }), 1200),
  )
}
