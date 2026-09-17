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

/** A span of time to the nearest five minutes: "8 h 35", "45 min", "6 h". */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes / 5) * 5)
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, '0')}`
}

export function formatTemp(celsius: number): string {
  return `${celsius < 0 ? '−' : ''}${Math.abs(celsius)}°`
}
