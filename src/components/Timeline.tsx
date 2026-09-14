import type { Minutes, Route, StopSeverity } from '../domain/types'
import { formatArrival } from '../domain/timing'
import { useT } from '../i18n'
import { stopLabel } from '../lib/route'
import { SEVERITY_BG } from '../lib/ui'
import { Card } from './Card'

interface Props {
  route: Route
  arrivals: Record<string, Minutes>
  stopSeverity: Record<string, StopSeverity>
  paceKnown: boolean
  onSelect: (stopId: string) => void
}

const BASE_HEIGHT: Record<StopSeverity, number> = { none: 18, mod: 50, high: 85, unknown: 70 }

export function Timeline({ route, arrivals, stopSeverity, paceKnown, onSelect }: Props) {
  const { t } = useT()
  const elevations = route.waypoints.map((w) => w.elevationM)
  const low = Math.min(...elevations)
  const high = Math.max(...elevations)

  const bars = route.stops.map((stop) => {
    const severity = stopSeverity[stop.id]
    const elevation = route.waypoints.find((w) => w.id === stop.waypointId)?.elevationM ?? low
    const height = Math.min(100, BASE_HEIGHT[severity] + ((elevation - low) / (high - low || 1)) * 15)
    return { stop, severity, height, label: stopLabel(stop, t), time: formatArrival(arrivals[stop.id]) }
  })

  return (
    <Card className="px-4 pt-4 pb-3.5">
      <div className="mb-3.5 flex items-baseline justify-between gap-3">
        <h2 className="text-[15px] font-semibold">{t('timeline.title')}</h2>
        <p className="text-right text-xs text-muted">{t('timeline.caption')}</p>
      </div>
      <div className="flex h-16 items-end gap-1.5">
        {bars.map(({ stop, severity, height, label, time }) => (
          <button
            key={stop.id}
            type="button"
            onClick={() => onSelect(stop.id)}
            aria-label={t('timeline.openMap', { stop: label, time })}
            className="flex h-full flex-1 items-end rounded-[4px]"
          >
            <span className={`block w-full rounded-[4px] ${SEVERITY_BG[severity]}`} style={{ height: `${height}%` }} />
          </button>
        ))}
      </div>
      <div aria-hidden="true" className="mt-2 flex gap-1.5 text-[11px] leading-[1.4] text-muted">
        {bars.map(({ stop, label, time }) => {
          const crux = stop.id === route.cruxStopId
          return (
            <div key={stop.id} className={`min-w-0 flex-1 text-center hyphens-auto ${crux ? 'font-semibold text-ink' : ''}`}>
              {time}
              <br />
              {/* Official place names are German; lets the browser hyphenate them correctly. */}
              <span lang={'place' in stop.label ? 'de' : undefined} className={crux ? '' : 'text-ink-2'}>
                {label}
              </span>
            </div>
          )
        })}
      </div>
      <p className="mt-3 border-t border-divider pt-3 text-[13px] leading-normal text-ink-3">
        {paceKnown ? t('timeline.footPace') : t('timeline.footCautious')}
      </p>
    </Card>
  )
}
