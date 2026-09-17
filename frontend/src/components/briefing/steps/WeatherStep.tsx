import { conditionsAt, gustAt } from '../../../domain/assessment'
import { formatArrival, formatClock } from '../../../domain/timing'
import { useT } from '../../../i18n'
import { formatInt, formatKm, formatTemp } from '../../../lib/format'
import { stopLabel } from '../../../lib/route'
import { OutcomeLine } from '../../OutcomeLine'
import { minuteAt } from '../stepMaps'
import type { StepProps } from './types'

function WindIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8" />
    </svg>
  )
}
function TempIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M14 14.8V4a2 2 0 1 0-4 0v10.8a4 4 0 1 0 4 0Z" />
    </svg>
  )
}
function RainIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z" />
    </svg>
  )
}

export function WeatherPanel({ view, model, progress }: StepProps) {
  const { t, lang } = useT()
  const { route, data, arrivals, evaluation } = view
  const minute = minuteAt(model, progress)

  return (
    <div className="flex flex-col gap-3">
      <OutcomeLine data={data} notEvaluatedCount={evaluation.notEvaluatedLegs.length} />
      <table className="w-full table-fixed text-left text-sm tabular-nums">
        <thead>
          <tr className="text-[11px] text-muted">
            <th className="w-14 py-1 font-normal">{t('brief.when')}</th>
            <th className="py-1 font-normal">{t('brief.where')}</th>
            <th className="w-[72px] py-1 text-right font-normal">
              <span className="inline-flex items-center gap-1">
                <WindIcon />
                km/h
                <span className="sr-only">{t('brief.gusts')}</span>
              </span>
            </th>
            <th className="w-12 py-1 text-right font-normal">
              <span className="inline-flex items-center gap-1">
                <TempIcon />
                <span className="sr-only">{t('brief.feelsLike')}</span>
              </span>
            </th>
            <th className="w-14 py-1 text-right font-normal">
              <span className="inline-flex items-center gap-1">
                <RainIcon />
                mm
                <span className="sr-only">{t('brief.rain')}</span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {route.stops.map((stop) => {
            const arrival = arrivals[stop.id]
            const reached = arrival <= minute + 0.5
            const unknown = evaluation.stopSeverity[stop.id] === 'unknown'
            const conditions = unknown ? null : conditionsAt(data, stop.id, arrival)
            const gust = unknown ? null : gustAt(data, stop.id, arrival)
            const crux = stop.id === route.cruxStopId
            const dash = <span className="text-faint">–</span>
            return (
              <tr
                key={stop.id}
                className={`border-t border-divider transition-opacity duration-300 ${reached ? 'opacity-100' : 'opacity-25'} ${crux ? 'font-semibold' : ''}`}
              >
                <td className="py-2 pr-2">{formatArrival(arrival)}</td>
                <td className="truncate py-2 pr-2" lang={'place' in stop.label ? 'de' : undefined}>
                  {stopLabel(stop, t)}
                </td>
                <td className={`py-2 text-right ${gust && gust.severity !== 'none' ? 'text-sev-high' : ''}`}>
                  {conditions?.gustKmh !== undefined ? formatInt(conditions.gustKmh) : dash}
                </td>
                <td className="py-2 text-right">
                  {conditions?.feelsLikeC !== undefined ? formatTemp(conditions.feelsLikeC) : dash}
                </td>
                <td className="py-2 text-right">
                  {conditions?.precipMm !== undefined ? formatKm(conditions.precipMm, lang) : dash}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="text-xs text-muted">
        {t('brief.weatherSource', { model: data.forecast.model, time: formatClock(data.forecast.issuedAt) })}
      </p>
    </div>
  )
}
