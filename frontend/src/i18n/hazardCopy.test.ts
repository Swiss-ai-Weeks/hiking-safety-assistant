import { describe, expect, it } from 'vitest'
import { hazards } from '../test/fixtures/assessment'
import type { HazardDef } from '../domain/types'
import { formatInt } from '../lib/format'
import { hazardKey, hazardParams, hazardText } from './hazardCopy'

const gusts = hazards.find((h) => h.kind === 'gusts')!

describe('hazardText', () => {
  it('quotes the figures from the facts', () => {
    expect(hazardText('en', gusts, 'body')).toBe(
      `Gusts up to 60 km/h at Hohtürli, ${formatInt(2778)} m. On exposed ground they cost balance from 40 km/h.`,
    )
    expect(hazardText('en', gusts, 'short')).toBe('gusts to 60 km/h from 11:00')
    expect(hazardText('en', gusts, 'liftsIf')).toBe('a later forecast shows gusts under 40 km/h at Hohtürli.')
  })

  it('falls back to the generic sentence when a fact is missing, never an empty placeholder', () => {
    const raisedByWarning: HazardDef = { ...gusts, facts: undefined, hasLiftsIf: false }

    expect(hazardKey('gusts', 'body', hazardParams(raisedByWarning, 'en'))).toBe('hazard.gusts.bodyGeneric')
    expect(hazardText('en', raisedByWarning, 'short')).toBe('strong gusts from 11:00')
    // "Lifts if" without its figure says nothing, so there is nothing to show.
    expect(hazardText('en', raisedByWarning, 'liftsIf')).toBeNull()
  })

  it('formats per language', () => {
    const cold: HazardDef = { ...gusts, kind: 'cold', facts: { feelsLikeC: -7 } }
    const showers: HazardDef = { ...gusts, kind: 'showers', facts: { precipMm: 1.5, thresholdMm: 0.5, freezingLevelM: 2900 } }

    expect(hazardText('fr', cold, 'short')).toBe('ressenti −7°, 11:00–14:00')
    expect(hazardText('fr', showers, 'body')).toContain('Jusqu’à 1,5 mm par heure')
    expect(hazardText('en', showers, 'body')).toContain('Up to 1.5 mm an hour')
  })
})
