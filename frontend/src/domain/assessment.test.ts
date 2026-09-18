import { describe, expect, it } from 'vitest'
import { getAssessmentData, type Scenario } from '../test/fixtures/mockApi'
import { oeschinenRoute as route } from '../test/fixtures/route-oeschinensee'
import { conditionsAt, evaluate, gustAt, hazardSeverityAt, nothingFlaggedRange } from './assessment'
import { computeArrivals } from './timing'
import type { PaceAnswer } from './types'

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

  it('treats intervals as half-open', () => {
    expect(hazardSeverityAt(gusts, 'hohturli', 630)).toBe('mod')
    expect(hazardSeverityAt(gusts, 'hohturli', 660)).toBe('high')
    expect(hazardSeverityAt(gusts, 'hohturli', 840)).toBe('none')
  })

  it('reports crux gusts from the forecast conditions, with the gust rule severity', () => {
    const data = getAssessmentData('assessed')
    expect(gustAt(data, 'hohturli', 700)).toEqual({ kmh: 55, severity: 'high' })
    expect(gustAt(data, 'hohturli', 600)).toEqual({ kmh: 25, severity: 'none' })
    expect(conditionsAt(data, 'hohturli', 700)?.feelsLikeC).toBe(-2)
  })

  it('has no crux numbers where there is no data', () => {
    const data = getAssessmentData('not_assessable')
    expect(gustAt(data, 'hohturli', 700)).toBeNull()
    expect(conditionsAt(data, 'hohturli', 700)).toBeNull()
  })
})
