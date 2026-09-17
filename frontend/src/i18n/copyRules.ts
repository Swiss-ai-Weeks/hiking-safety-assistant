import type { Lang } from '../domain/types'

/**
 * The copy rules as patterns, shared by `copy-rules.test.ts` and the runtime check on generated text.
 * `backend/app/narration/guard.py` holds the same lists, translated to Python's `re`.
 */

/** The UI never gives a verdict: no "safe", "fine", "clear to" (spec copy rules). */
export const BANNED: Record<Lang, RegExp[]> = {
  en: [/\bsafe(ly)?\b/i, /\bfine\b/i, /\bclear to\b/i, /\bgood to go\b/i, /\bgo ahead\b/i],
  fr: [/(^|[^\p{L}])sûre?s?(?=[^\p{L}]|$)/iu, /sans danger/i, /en sécurité/i, /vous pouvez y aller/i],
}

/**
 * Stricter, for text a model wrote: a template is reviewed once, generated text is new every time.
 * Reassurance in other words, and telling the hiker whether to go.
 */
export const GENERATED_BANNED: Record<Lang, RegExp[]> = {
  en: [
    /\bno (real )?(risk|danger|hazard)s?\b/i,
    /\brisk[- ]free\b/i,
    /\bnot dangerous\b/i,
    /\bnothing to worry\b/i,
    /\bguarantee/i,
    /\b(do not|don't|should not|shouldn't) (go|hike|attempt)\b/i,
  ],
  fr: [/sans risque/i, /aucun (risque|danger)/i, /pas dangereu/i, /garanti/i, /(n'|ne )(allez|partez|tentez) pas/i],
}

/** Every pattern a generated sentence breaks, as strings for a test message. Empty when it breaks none. */
export function verdictsIn(text: string, lang: Lang): string[] {
  return [...BANNED[lang], ...GENERATED_BANNED[lang]].filter((pattern) => pattern.test(text)).map(String)
}
