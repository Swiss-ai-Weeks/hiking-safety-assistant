import type { AssessmentData } from '../../domain/types'
import { alternatives, conditionsFor, forecast, gaps, hazards, partialNotEvaluated } from './assessment'

/** The states the briefing renders. Test data only: the app shows what the backend computes. */
export type Scenario = 'assessed' | 'partial' | 'not_assessable' | 'stale'

/** The same authored assessments as `backend/tests/authored.py`, for tests. */
export function getAssessmentData(scenario: Scenario): AssessmentData {
  switch (scenario) {
    case 'not_assessable':
      return {
        outcome: 'not_assessable',
        stale: false,
        forecast: { ...forecast, unavailableReason: 'source' },
        hazards: [],
        gaps: [],
        alternatives: [],
        notEvaluated: [],
        conditions: {},
      }
    case 'partial': {
      const partialHazards = hazards.filter((h) => h.kind !== 'gusts')
      return {
        outcome: 'partial',
        stale: false,
        forecast,
        hazards: partialHazards,
        gaps,
        alternatives: alternatives.filter((a) => a.kind !== 'startEarlier'),
        notEvaluated: partialNotEvaluated,
        conditions: conditionsFor(partialHazards),
      }
    }
    case 'stale':
    case 'assessed':
      return {
        outcome: 'assessed',
        stale: scenario === 'stale',
        forecast,
        hazards,
        gaps,
        alternatives,
        notEvaluated: [],
        conditions: conditionsFor(hazards),
      }
  }
}
