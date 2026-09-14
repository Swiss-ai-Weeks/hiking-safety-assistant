import { describe, expect, it } from 'vitest'
import { getAssessmentData, resolveScenario } from '../data/mock/mockApi'
import { oeschinenRoute as route } from '../data/mock/route-oeschinensee'
import { evaluate, gustAt, hazardSeverityAt, nothingFlaggedRange } from './assessment'
import { computeArrivals } from './timing'
import type { PaceAnswer, Scenario } from './types'

const evaluateFor = (start: number, pace: PaceAnswer | null, scenario: Scenario = 'assessed') => {
  const data = getAssessmentData(scenario)
  const arrivals = computeArrivals(route, start, pace)
  return { data, arrivals, evaluation: evaluate(route, arrivals, data) }
}

describe('evaluate', () => {
  it('matches the spec timeline for 07:30 at a cautious pace', () => {
    const { evaluation } = evaluateFor(450, null)
    expect(evaluation.stopSeverity).toEqual({
      'lake-start': 'none',
      ober: 'none',
      moraine: 'mod',
      hohturli: 'high',
      hutte: 'high',
      descent: 'mod',
      'lake-end': 'none',
    })
    expect(evaluation.flagged.map((f) => [f.hazard.id, f.severity])).toEqual([
      ['gusts-hohturli', 'high'],
      ['showers-descent', 'mod'],
    ])
  })

  it('colours map legs by their highest severity and names the cause (spec 02c)', () => {
    const { evaluation } = evaluateFor(450, null)
    expect(evaluation.legSeverity).toEqual({
      'lake-ober': 'none',
      'ober-moraine': 'mod',
      'moraine-hohturli': 'high',
      'hohturli-hutte': 'high',
    })
    expect(evaluation.legCause['ober-moraine']?.kind).toBe('showers')
    expect(evaluation.legCause['moraine-hohturli']?.kind).toBe('gusts')
    expect(evaluation.legCause['lake-ober']).toBeNull()
  })

  it('names the opening stretch with nothing flagged', () => {
    const { evaluation } = evaluateFor(450, null)
    expect(nothingFlaggedRange(route, evaluation.stopSeverity)).toEqual({ from: 'lake-start', to: 'ober' })
  })

  it('updates flags when the start moves earlier', () => {
    const { evaluation } = evaluateFor(390, '5to6')
    expect(evaluation.stopSeverity.hohturli).toBe('none')
    expect(evaluation.stopSeverity.hutte).toBe('mod')
    expect(evaluation.flagged.map((f) => [f.hazard.id, f.severity])).toEqual([['gusts-hohturli', 'mod']])
  })

  it('marks sections without data as not evaluated instead of reassuring', () => {
    const { evaluation } = evaluateFor(450, null, 'partial')
    expect(evaluation.stopSeverity.hohturli).toBe('unknown')
    expect(evaluation.legSeverity['moraine-hohturli']).toBe('unknown')
    expect(evaluation.notEvaluatedLegs.map((l) => l.id)).toEqual(['moraine-hohturli', 'hohturli-hutte'])
    expect(evaluation.flagged.map((f) => f.hazard.id)).toEqual(['showers-descent'])
  })
})

describe('hazard helpers', () => {
  const [gusts] = getAssessmentData('assessed').hazards

  it('reads moderate during the build-up and none outside the window', () => {
    expect(hazardSeverityAt(gusts, 'hohturli', 645)).toBe('mod')
    expect(hazardSeverityAt(gusts, 'hohturli', 700)).toBe('high')
    expect(hazardSeverityAt(gusts, 'hohturli', 600)).toBe('none')
    expect(hazardSeverityAt(gusts, 'ober', 700)).toBe('none')
  })

  it('reports crux gusts for the crux card', () => {
    expect(gustAt([gusts], 'hohturli', 700)).toEqual({ kmh: 55, severity: 'high' })
  })
})

describe('scenarios', () => {
  it('lets query parameters override the settings scenario', () => {
    expect(resolveScenario('assessed', new URLSearchParams('outcome=not_assessable'))).toBe('not_assessable')
    expect(resolveScenario('partial', new URLSearchParams('stale=1'))).toBe('stale')
    expect(resolveScenario('partial', new URLSearchParams('outcome=nonsense'))).toBe('partial')
  })

  it('shows no hazards or recommendations when not assessable (02b)', () => {
    const data = getAssessmentData('not_assessable')
    expect(data.outcome).toBe('not_assessable')
    expect(data.hazards).toEqual([])
    expect(data.alternatives).toEqual([])
  })

  it('keeps the outcome but flags staleness', () => {
    const data = getAssessmentData('stale')
    expect(data.outcome).toBe('assessed')
    expect(data.stale).toBe(true)
  })
})
