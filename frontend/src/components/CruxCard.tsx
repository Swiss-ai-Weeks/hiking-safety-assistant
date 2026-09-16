import type { Minutes, Severity } from '../domain/types'
import { formatArrival, formatClock } from '../domain/timing'
import { useT } from '../i18n'
import { formatInt, formatTemp } from '../lib/format'

interface Props {
  place: string
  elevationM: number
  arrival: Minutes
  gust: { kmh: number; severity: Severity } | null
  feelsLikeC: number | null
  showersFrom: Minutes | null
  stale: boolean
}

export function CruxCard({ place, elevationM, arrival, gust, feelsLikeC, showersFrom, stale }: Props) {
  const { t, tr } = useT()
  const tiles = [
    {
      label: t('crux.gusts'),
      value: gust ? `${gust.kmh} km/h` : t('crux.noData'),
      warn: gust !== null && gust.severity !== 'none',
    },
    { label: t('crux.feelsLike'), value: feelsLikeC === null ? t('crux.noData') : formatTemp(feelsLikeC), warn: false },
    { label: t('crux.showers'), value: showersFrom === null ? '—' : formatClock(showersFrom), warn: false },
  ]

  return (
    <section className="flex flex-col gap-3 rounded-crux bg-ink px-5 pt-5 pb-[18px] text-white">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold tracking-[0.08em] text-crux-label uppercase">{t('crux.eyebrow')}</p>
        {stale && (
          <span className="rounded-full bg-sev-mod px-2 py-0.5 text-[11px] font-semibold text-ink">{t('crux.stale')}</span>
        )}
      </div>
      <div>
        <h2 className="font-serif text-[26px] leading-[1.15] font-medium">
          {place}, {formatInt(elevationM)} m
        </h2>
        <p className="mt-1 text-[15px] text-crux-body">
          {tr('crux.arrival', { time: <strong className="font-semibold text-white">{formatArrival(arrival)}</strong> })}
        </p>
      </div>
      <dl className="flex gap-2.5">
        {tiles.map((tile) => (
          <div key={tile.label} className="min-w-0 flex-1 rounded-control bg-crux-tile px-3 py-2.5">
            <dt className="text-[11px] text-crux-muted">{tile.label}</dt>
            <dd className={`truncate text-xl font-semibold ${tile.warn ? 'text-crux-warn' : ''}`}>{tile.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
