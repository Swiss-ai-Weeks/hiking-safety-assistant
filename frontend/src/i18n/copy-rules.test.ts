import { describe, expect, it } from 'vitest'
import { en, type MessageKey } from './en'
import { fr } from './fr'
import type { HazardDef, Lang, Narration } from '../domain/types'
import { BANNED, verdictsIn } from './copyRules'
import { BASE_PLACEHOLDERS, FACT_PLACEHOLDERS, hazardParams, narratedBody } from './hazardCopy'

/**
 * What the backend serves as narration for the authored test hazards, in both languages: model answers put
 * through its parser and guard (`backend/tests/test_narrator.py` checks the `served` part is exactly
 * what they produce). `pytest --record` replaces the answers with a real model's.
 */
type NarrationFixture = { recorded: boolean; hazards: HazardDef[]; served: Record<Lang, Narration> }
const narrationFixtures = import.meta.glob<NarrationFixture>('../../../backend/tests/fixtures/narration_*.json', {
  eager: true,
  import: 'default',
})

const PLACE_NAMES = ['Oeschinensee', 'Oberbärgli', 'Hohtürli', 'Blüemlisalphütte', 'Hütte']

const keys = Object.keys(en) as MessageKey[]
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('copy rules', () => {
  for (const [lang, dict] of [
    ['en', en],
    ['fr', fr],
  ] as const) {
    it(`${lang} never uses verdict words`, () => {
      const hits = keys.flatMap((key) =>
        BANNED[lang].filter((pattern) => pattern.test(dict[key])).map((pattern) => `${key} ${pattern}: ${dict[key]}`),
      )
      expect(hits).toEqual([])
    })
  }

  it('fr uses the same placeholders as en', () => {
    const mismatches = keys.filter((key) => placeholders(en[key]).join() !== placeholders(fr[key]).join())
    expect(mismatches).toEqual([])
  })

  it('never translates place names', () => {
    const missing = keys.flatMap((key) =>
      PLACE_NAMES.filter((place) => en[key].includes(place) && !fr[key].includes(place)).map((place) => `${key}: ${place}`),
    )
    expect(missing).toEqual([])
  })

  describe('hazard copy', () => {
    const hazardKeys = keys.filter((key) => key.startsWith('hazard.'))

    it('carries no figures: every number comes from the facts', () => {
      const withDigits = hazardKeys.flatMap((key) =>
        [en[key], fr[key]].filter((text) => /\d/.test(text)).map((text) => `${key}: ${text}`),
      )
      expect(withDigits).toEqual([])
    })

    it('uses only placeholders the facts can fill', () => {
      const known = new Set([...BASE_PLACEHOLDERS, ...Object.keys(FACT_PLACEHOLDERS)])
      const unknown = hazardKeys.flatMap((key) => placeholders(en[key]).filter((name) => !known.has(name)).map((name) => `${key}: {${name}}`))
      expect(unknown).toEqual([])
    })

    it('has a generic fallback for every string that needs a fact', () => {
      const facts = new Set(Object.keys(FACT_PLACEHOLDERS))
      const missing = hazardKeys.filter(
        (key) =>
          !key.endsWith('Generic') &&
          !key.endsWith('.liftsIf') &&
          placeholders(en[key]).some((name) => facts.has(name)) &&
          !(`${key}Generic` in en),
      )
      expect(missing).toEqual([])
      const genericNeedingFacts = hazardKeys.filter(
        (key) => key.endsWith('Generic') && placeholders(en[key]).some((name) => facts.has(name)),
      )
      expect(genericNeedingFacts).toEqual([])
    })
  })

  describe('generated hazard copy', () => {
    const fixtures = Object.entries(narrationFixtures)

    it('has served narration to check', () => {
      expect(fixtures.length).toBeGreaterThan(0)
      for (const [, fixture] of fixtures) {
        const bodies = (['en', 'fr'] as const).flatMap((lang) => fixture.served[lang].hazards.filter((h) => h.body))
        expect(bodies.length).toBeGreaterThan(0)
      }
    })

    for (const lang of ['en', 'fr'] as const) {
      it(`${lang}: every served body carries no figures, only fillable placeholders and no verdict`, () => {
        const problems = fixtures.flatMap(([file, fixture]) =>
          fixture.served[lang].hazards.flatMap(({ id, body }) => {
            if (!body) return []
            const hazard = fixture.hazards.find((h) => h.id === id)
            if (!hazard) return [`${file} ${id}: no such hazard`]
            const params = hazardParams(hazard, lang)
            return [
              ...(/\d/.test(body) ? [`${id}: figure in "${body}"`] : []),
              ...placeholders(body)
                .filter((name) => !(name in params))
                .map((name) => `${id}: {${name}} unfillable`),
              ...verdictsIn(body, lang).map((pattern) => `${id} ${pattern}: ${body}`),
              ...(narratedBody(lang, hazard, body) === null ? [`${id}: refused at display: ${body}`] : []),
            ]
          }),
        )
        expect(problems).toEqual([])
      })
    }
  })
})
