import { useState } from 'react'
import { PillButton } from '../components/Button'
import { useBriefingModel } from '../components/briefing/model'
import { RouteMap } from '../components/briefing/RouteMap'
import { planStepMap } from '../components/briefing/stepMaps'
import { ChevronRight } from '../components/icons'
import { ScreenHeader } from '../components/ScreenHeader'
import { SeverityDot, SeverityLegend } from '../components/Severity'
import { formatArrival, formatClock } from '../domain/timing'
import type { LatLng } from '../domain/types'
import { useAssessmentView } from '../hooks/useAssessmentView'
import { useT } from '../i18n'
import { hazardText } from '../i18n/hazardCopy'
import { formatKm } from '../lib/format'
import { routeName, stopWaypoint } from '../lib/route'
import { usePlan, useTurnaround } from '../store/plan'

type LocateState = 'idle' | 'locating' | 'failed'

/** The whole route with its segments, from field mode: where the way down goes, and where you are. */
export function RouteMapScreen() {
  const { t, lang } = useT()
  const view = useAssessmentView()
  const { route, arrivals, evaluation, data, paceAnswer } = view
  const model = useBriefingModel(view)
  const turnaround = useTurnaround()
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const [focus, setFocus] = useState<LatLng | null>(null)
  const [me, setMe] = useState<LatLng | null>(null)
  const [locate, setLocate] = useState<LocateState>('idle')
  const forecastTime = formatClock(data.forecast.issuedAt)
  const mapState = planStepMap({ view, model, progress: 1, t, turnaround })

  const locateMe = () => {
    if (!('geolocation' in navigator)) {
      setLocate('failed')
      return
    }
    setLocate('locating')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const here: LatLng = [pos.coords.latitude, pos.coords.longitude]
        setMe(here)
        setFocus(here)
        setLocate('idle')
      },
      () => setLocate('failed'),
      { timeout: 10_000, maximumAge: 60_000 },
    )
  }

  return (
    <div className="flex h-dvh flex-col">
      <ScreenHeader
        backTo={hikeStarted ? '/field' : '/briefing'}
        title={t('map.title')}
        subtitle={t('map.subtitle', { route: routeName(route), km: formatKm(route.distanceKm, lang) })}
        action={
          <PillButton onClick={locateMe} disabled={locate === 'locating'}>
            {locate === 'locating' ? t('map.locating') : locate === 'failed' ? t('map.locateFailed') : t('map.locate')}
          </PillButton>
        }
      />

      <RouteMap
        route={route}
        className="min-h-0 flex-1"
        legPaint={mapState.legPaint}
        pins={mapState.pins}
        me={me}
        focus={focus}
      >
        <SeverityLegend className="absolute top-3 left-3 z-[500]" />
      </RouteMap>

      <section className="relative z-10 flex flex-col gap-0.5 rounded-t-sheet border-t border-line bg-card px-[18px] pt-2.5 pb-[max(env(safe-area-inset-bottom),28px)] shadow-[0_-6px_20px_rgba(0,0,0,0.06)]">
        <div aria-hidden="true" className="mx-auto mb-2.5 h-1 w-9 rounded-full bg-grip" />
        <div className="mb-1.5 flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold">{t('map.segments')}</h2>
          <p className="text-right text-xs text-muted">
            {paceAnswer ? t('map.captionPace', { time: forecastTime }) : t('map.captionCautious', { time: forecastTime })}
          </p>
        </div>
        <ul>
          {route.legs.map((leg) => {
            const from = stopWaypoint(route, leg.fromStop)
            const to = stopWaypoint(route, leg.toStop)
            const severity = evaluation.legSeverity[leg.id]
            const cause = evaluation.legCause[leg.id]
            const note =
              severity === 'unknown'
                ? t('map.notEvaluated')
                : cause
                  ? hazardText(lang, cause, 'short')
                  : t('map.nothingAsOf', { time: forecastTime })
            const grade = leg.cables ? `${leg.grade}, ${t('map.cables')}` : leg.grade
            return (
              <li key={leg.id} className="border-b border-divider last:border-0">
                <button
                  type="button"
                  onClick={() => setFocus([(from.latLng[0] + to.latLng[0]) / 2, (from.latLng[1] + to.latLng[1]) / 2])}
                  className="flex w-full items-center gap-3 py-2.5 text-left"
                >
                  <SeverityDot severity={severity} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-medium">
                      {from.name} → {to.name}
                    </span>
                    <span className="block text-xs text-muted">
                      {formatArrival(arrivals[leg.fromStop])}–{formatArrival(arrivals[leg.toStop])} · {grade} · {note}
                    </span>
                  </span>
                  <ChevronRight className="shrink-0 text-chevron" />
                </button>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
