import { clockOf, formatClock } from '../domain/timing'
import type { Lang } from '../domain/types'

const LOCALES: Record<Lang, string> = { en: 'en-GB', fr: 'fr-CH' }

function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** "Sat 19 Sep" / "sam. 19 sept." */
export function formatShortDate(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALES[lang], { weekday: 'short', day: 'numeric', month: 'short' })
    .format(parseISODate(iso))
    .replace(',', '')
}

/** "6 Sep" / "6 sept." */
export function formatDayMonth(iso: string | Date, lang: Lang): string {
  const date = typeof iso === 'string' ? parseISODate(iso) : iso
  return new Intl.DateTimeFormat(LOCALES[lang], { day: 'numeric', month: 'short' }).format(date)
}

/** "Saturday" / "samedi" */
export function formatWeekday(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALES[lang], { weekday: 'long' }).format(parseISODate(iso))
}

/** "18 Sep 21:40" */
export function formatDateTime(timestamp: number, lang: Lang): string {
  const date = new Date(timestamp)
  return `${formatDayMonth(date, lang)} ${formatClock(clockOf(date))}`
}

/** Thousands grouped with a no-break space, as in "2 778 m". */
export function formatInt(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function formatKm(n: number, lang: Lang): string {
  return new Intl.NumberFormat(LOCALES[lang], { maximumFractionDigits: 1 }).format(n)
}

export function formatTemp(celsius: number): string {
  return `${celsius < 0 ? '−' : ''}${Math.abs(celsius)}°`
}
