import { describe, expect, it } from 'vitest'
import { oeschinenRoute as route } from '../data/mock/route-oeschinensee'
import type { PaceAnswer } from './types'
import {
  computeArrivals,
  fieldEstimate,
  formatArrival,
  formatClock,
  parseClock,
  turnaroundStatus,
} from './timing'

const arrival = (start: number, pace: PaceAnswer | null, stopId: string) =>
  formatArrival(computeArrivals(route, start, pace)[stopId])

describe('computeArrivals', () => {
  it('assumes a cautious pace until the hiker answers (spec 02)', () => {
    expect(arrival(450, null, 'ober')).toBe('09:30')
    expect(arrival(450, null, 'moraine')).toBe('10:40')
    expect(arrival(450, null, 'hohturli')).toBe('11:40')
    expect(arrival(450, null, 'hutte')).toBe('12:00')
    expect(arrival(450, null, 'lake-end')).toBe('16:15')
  })

  it('recomputes with the reference-class answer (spec 03)', () => {
    expect(arrival(450, '5to6', 'hohturli')).toBe('11:20')
    expect(arrival(450, '5to6', 'lake-end')).toBe('15:40')
  })

  it('puts the crux at 10:40 with the suggested 06:30 start', () => {
    expect(arrival(390, null, 'hohturli')).toBe('10:40')
  })

  it('orders paces from fastest to slowest', () => {
    const at = (pace: PaceAnswer) => computeArrivals(route, 450, pace).hohturli
    expect(at('under5')).toBeLessThan(at('5to6'))
    expect(at('5to6')).toBeLessThan(at('over7'))
  })

  it('does not scale breaks with pace', () => {
    const fast = computeArrivals(route, 450, 'under5')
    expect(fast.descent - fast.hutte).toBeCloseTo(45 + 45 * 0.85)
  })
})

describe('clock helpers', () => {
  it('parses valid times and rejects invalid ones', () => {
    expect(parseClock('06:30')).toBe(390)
    expect(parseClock('7:05')).toBe(425)
    expect(parseClock('24:00')).toBeNull()
    expect(parseClock('07:60')).toBeNull()
    expect(parseClock('soon')).toBeNull()
  })

  it('wraps around midnight', () => {
    expect(formatClock(-10)).toBe('23:50')
    expect(formatClock(1450)).toBe('00:10')
  })
})

describe('field mode', () => {
  it('is ahead of the 11:30 turnaround with a 06:30 start (spec 04)', () => {
    const { now, eta } = fieldEstimate(route, 390)
    expect(formatClock(now)).toBe('10:52')
    expect(formatClock(eta)).toBe('11:15')
    expect(turnaroundStatus(eta, route.turnaroundDefault)).toBe('ahead')
  })

  it('is past the turnaround with a 07:30 start', () => {
    const { eta } = fieldEstimate(route, 450)
    expect(turnaroundStatus(eta, route.turnaroundDefault)).toBe('behind')
  })
})
