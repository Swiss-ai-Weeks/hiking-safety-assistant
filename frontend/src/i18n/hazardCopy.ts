import { formatClock } from '../domain/timing'
import type { HazardDef, HazardFacts, HazardKind, Lang } from '../domain/types'
import { formatInt, formatKm, formatTemp } from '../lib/format'
import { en, type MessageKey } from './en'
import { translate } from './index'

/**
 * Hazard text with its numbers filled in from `HazardDef.facts`.
 *
 * The hazard strings carry placeholders and never figures (`copy-rules.test.ts` checks), so a
 * number on screen is always one the engine computed. A string whose facts are missing — a hazard
 * raised by a warning alone, or a source that did not report a level — falls back to its
 * `…Generic` variant, which needs none, rather than showing `{gust}` or inventing a value.
 */

/** Each fact placeholder, the fact it needs, and how it is written. */
export const FACT_PLACEHOLDERS: Record<string, { fact: keyof HazardFacts; format: (n: number, lang: Lang) => string }> = {
  gust: { fact: 'gustKmh', format: formatInt },
  threshold: { fact: 'thresholdKmh', format: formatInt },
  precip: { fact: 'precipMm', format: formatKm },
  thresholdMm: { fact: 'thresholdMm', format: formatKm },
  thunder: { fact: 'thunderPct', format: formatInt },
  feelsLike: { fact: 'feelsLikeC', format: formatTemp },
  freezingLevel: { fact: 'freezingLevelM', format: formatInt },
  snowline: { fact: 'snowlineM', format: formatInt },
  cloudBase: { fact: 'cloudBaseM', format: formatInt },
  elevation: { fact: 'elevationM', format: formatInt },
  sunset: { fact: 'sunset', format: formatClock },
}

/** Placeholders every hazard string may use without facts. */
export const BASE_PLACEHOLDERS = ['place', 'from', 'to']

export type HazardPart = 'title' | 'body' | 'liftsIf' | 'short' | 'watch'

const placeholdersOf = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1])

export function hazardParams(hazard: HazardDef, lang: Lang): Record<string, string> {
  const params: Record<string, string> = {
    from: formatClock(hazard.window.from),
    to: formatClock(hazard.window.to),
  }
  if (hazard.place) params.place = hazard.place
  for (const [name, { fact, format }] of Object.entries(FACT_PLACEHOLDERS)) {
    const value = hazard.facts?.[fact]
    if (value !== undefined) params[name] = format(value, lang)
  }
  return params
}

/**
 * The key to render for one part of a hazard: the specific string when every placeholder it uses
 * has a value, else its generic variant. `null` when neither can be filled — for "lifts if", that
 * means the line is left out, since a condition without its figure says nothing.
 */
export function hazardKey(kind: HazardKind, part: HazardPart, params: Record<string, string>): MessageKey | null {
  const specific = `hazard.${kind}.${part}` as MessageKey
  const generic = `hazard.${kind}.${part}Generic`
  for (const key of [specific, generic]) {
    if (key in en && placeholdersOf(en[key as MessageKey]).every((name) => name in params)) return key as MessageKey
  }
  return null
}

/** One part of a hazard, rendered in `lang`; `null` when it cannot be said with the facts at hand. */
export function hazardText(lang: Lang, hazard: HazardDef, part: HazardPart): string | null {
  const params = hazardParams(hazard, lang)
  const key = hazardKey(hazard.kind, part, params)
  return key === null ? null : translate(lang, key, params)
}
