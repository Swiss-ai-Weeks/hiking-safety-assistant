import type { AssessmentData, Scenario } from '../../domain/types'
import { alternatives, forecast, gaps, hazards, partialNotEvaluated } from './assessment'

/** Same scenarios the backend serves (backend/app/mock_data.py), for pure domain tests. */
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
