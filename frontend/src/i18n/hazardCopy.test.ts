import { describe, expect, it } from 'vitest'
import { hazards } from '../test/fixtures/assessment'
import type { HazardDef } from '../domain/types'
import { formatInt } from '../lib/format'
import { hazardKey, hazardParams, hazardText, narratedBody } from './hazardCopy'

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

describe('narratedBody', () => {
  it('fills a generated body from the facts, formatted for the language', () => {
    expect(narratedBody('en', gusts, 'Gusts to {gust} km/h at {place} from {from}.')).toBe(
      'Gusts to 60 km/h at Hohtürli from 11:00.',
    )
    expect(narratedBody('fr', gusts, 'Rafales à {gust} km/h au {place}, {elevation} m.')).toBe(
      `Rafales à 60 km/h au Hohtürli, ${formatInt(2778)} m.`,
    )
  })

  it('refuses what the copy rules forbid, so the template shows instead', () => {
    const refused = [
      undefined,
      '',
      'Gusts to 60 km/h at {place}.',
      'Gusts to {gust} km/h, fine after {to}.',
      'Rain up to {precip} mm.',
      'Gusts at {place {gust}.',
      'You should not go past {place}.',
    ]
    expect(refused.map((body) => narratedBody('en', gusts, body))).toEqual(refused.map(() => null))
    expect(narratedBody('fr', gusts, 'Aucun risque au {place}.')).toBeNull()
  })
})
