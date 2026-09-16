import type { AssessmentData, Scenario } from '../../domain/types'
import { alternatives, conditionsFor, forecast, gaps, hazards, partialNotEvaluated } from './assessment'

/** Same scenarios the backend serves (backend/app/mock_data.py), for pure domain tests. */
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
