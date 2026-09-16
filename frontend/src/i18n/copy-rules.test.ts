import { describe, expect, it } from 'vitest'
import { en, type MessageKey } from './en'
import { fr } from './fr'
import { BASE_PLACEHOLDERS, FACT_PLACEHOLDERS } from './hazardCopy'

/** The UI never gives a verdict: no "safe", "fine", "clear to" (spec copy rules). */
const BANNED: Record<'en' | 'fr', RegExp[]> = {
  en: [/\bsafe(ly)?\b/i, /\bfine\b/i, /\bclear to\b/i, /\bgood to go\b/i, /\bgo ahead\b/i],
  fr: [/(^|[^\p{L}])sûre?s?(?=[^\p{L}]|$)/iu, /sans danger/i, /en sécurité/i, /vous pouvez y aller/i],
}

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
})
