import type { Scenario } from '../domain/types'

const SCENARIOS: Scenario[] = ['assessed', 'partial', 'not_assessable', 'stale']

/** `?outcome=` and `?stale=1` override the scenario chosen in settings. */
export function resolveScenario(fromSettings: Scenario, params: URLSearchParams): Scenario {
  if (params.get('stale') === '1') return 'stale'
  const outcome = params.get('outcome')
  return SCENARIOS.includes(outcome as Scenario) ? (outcome as Scenario) : fromSettings
}
