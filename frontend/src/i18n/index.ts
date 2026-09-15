import { createElement, Fragment, useMemo, type ReactNode } from 'react'
import type { Lang } from '../domain/types'
import { usePlan } from '../store/plan'
import { en, type MessageKey } from './en'
import { fr } from './fr'

export type { MessageKey }

const dictionaries = { en, fr }

type Params = Record<string, string | number>

/** Fills `{name}` placeholders. Unknown placeholders are left visible. */
export function translate(lang: Lang, key: MessageKey, params?: Params): string {
  return dictionaries[lang][key].replace(/\{(\w+)\}/g, (match, name: string) =>
    params && name in params ? String(params[name]) : match,
  )
}

/** Like `translate`, but placeholders may be React nodes (links, emphasis). */
export function translateRich(lang: Lang, key: MessageKey, params: Record<string, ReactNode>): ReactNode {
  const parts = dictionaries[lang][key].split(/(\{\w+\})/g)
  return createElement(
    Fragment,
    null,
    ...parts.map((part, i) => {
      const name = /^\{(\w+)\}$/.exec(part)?.[1]
      return createElement(Fragment, { key: i }, name !== undefined && name in params ? params[name] : part)
    }),
  )
}

export function useT() {
  const lang = usePlan((s) => s.lang)
  return useMemo(
    () => ({
      lang,
      t: (key: MessageKey, params?: Params) => translate(lang, key, params),
      tr: (key: MessageKey, params: Record<string, ReactNode>) => translateRich(lang, key, params),
    }),
    [lang],
  )
}

export type Translate = ReturnType<typeof useT>['t']
