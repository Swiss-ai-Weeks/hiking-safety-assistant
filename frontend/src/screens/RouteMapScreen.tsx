import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet'
import { PillButton } from '../components/Button'
import { ChevronRight } from '../components/icons'
import { ScreenHeader } from '../components/ScreenHeader'
import { SeverityDot, SeverityLegend } from '../components/Severity'
import { formatArrival, formatClock } from '../domain/timing'
import type { LatLng } from '../domain/types'
import { useAssessmentView } from '../hooks/useAssessmentView'
import { useT } from '../i18n'
import { formatInt, formatKm } from '../lib/format'
import { routeName, stopWaypoint } from '../lib/route'
import { SEVERITY_STROKE } from '../lib/ui'
import { useTurnaround } from '../store/plan'

/** Label offsets relative to each waypoint, as in the spec's map prototype. */
const LABEL_POSITION: Record<string, string> = {
  lake: 'left:-6px;bottom:12px',
  ober: 'right:10px;bottom:10px',
  hohturli: 'right:-6px;top:14px',
  hutte: 'right:-4px;bottom:12px',
}

const dotIcon = L.divIcon({ className: '', html: '<div class="map-dot"></div>', iconSize: [12, 12], iconAnchor: [6, 6] })
const youIcon = L.divIcon({
  className: '',
  html: '<div class="map-dot" style="border-color:oklch(0.5 0.12 300)"></div>',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
})

function labelIcon(text: string, variant: '' | 'crux' | 'turn', position: string) {
  const el = document.createElement('div')
  el.className = `map-label${variant ? ` map-label--${variant}` : ''}`
  el.setAttribute('style', position)
  el.textContent = text
  return L.divIcon({ className: '', html: el, iconSize: [0, 0], iconAnchor: [0, 0] })
}

function PanTo({ target }: { target: LatLng | null }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.panTo(target, { animate: true })
  }, [map, target])
  return null
}

type LocateState = 'idle' | 'locating' | 'failed'

export function RouteMapScreen() {
  const { t, lang } = useT()
  const { route, arrivals, evaluation, data, paceAnswer, search, params } = useAssessmentView()
  const turnaround = useTurnaround()
  const [focus, setFocus] = useState<LatLng | null>(null)
  const [me, setMe] = useState<LatLng | null>(null)
  const [locate, setLocate] = useState<LocateState>('idle')

  const bounds = useMemo(() => L.latLngBounds(route.waypoints.map((w) => w.latLng)), [route])
  const forecastTime = formatClock(data.forecast.issuedAt)
  const backTo = params.get('from') === 'field' ? '/field' : { pathname: '/assessment', search }

  const labels = useMemo(() => {
    const crux = stopWaypoint(route, route.cruxStopId)
    return [
      { id: 'lake', icon: labelIcon(`${route.fromName} · ${formatArrival(arrivals['lake-start'])}`, '', LABEL_POSITION.lake) },
      {
        id: 'ober',
        icon: labelIcon(`${route.bailoutName} · ${formatArrival(arrivals.ober)} · ${t('map.bailout')}`, 'turn', LABEL_POSITION.ober),
      },
      {
        id: crux.id,
        icon: labelIcon(
          `${crux.name} ${formatInt(crux.elevationM)} m · ${formatArrival(arrivals[route.cruxStopId])} · ${t('map.turnBy', { time: formatClock(turnaround) })}`,
          'crux',
          LABEL_POSITION.hohturli,
        ),
      },
      { id: 'hutte', icon: labelIcon(route.toName, '', LABEL_POSITION.hutte) },
    ]
  }, [route, arrivals, turnaround, t])

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
        backTo={backTo}
        title={t('map.title')}
        subtitle={t('map.subtitle', { route: routeName(route), km: formatKm(route.distanceKm, lang) })}
        action={
          <PillButton onClick={locateMe} disabled={locate === 'locating'}>
            {locate === 'locating' ? t('map.locating') : locate === 'failed' ? t('map.locateFailed') : t('map.locate')}
          </PillButton>
        }
      />

      <div className="relative isolate min-h-0 flex-1">
        <MapContainer
          bounds={bounds}
          boundsOptions={{ paddingTopLeft: [24, 70], paddingBottomRight: [24, 40] }}
          zoomControl={false}
          className="route-map absolute inset-0 h-full w-full"
        >
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            maxZoom={17}
          />
          {route.legs.map((leg) => {
            const positions = [stopWaypoint(route, leg.fromStop).latLng, stopWaypoint(route, leg.toStop).latLng]
            const severity = evaluation.legSeverity[leg.id]
            return (
              <Fragment key={leg.id}>
                <Polyline positions={positions} pathOptions={{ color: '#fff', weight: 9, opacity: 0.9 }} />
                <Polyline
                  positions={positions}
                  pathOptions={{
                    color: SEVERITY_STROKE[severity],
                    weight: 5,
                    dashArray: severity === 'unknown' ? '6 8' : undefined,
                  }}
                />
              </Fragment>
            )
          })}
          {route.waypoints.map((w) => (
            <Marker key={w.id} position={w.latLng} icon={dotIcon} interactive={false} keyboard={false} />
          ))}
          {labels.map((label) => (
            <Marker
              key={`${label.id}-label`}
              position={route.waypoints.find((w) => w.id === label.id)!.latLng}
              icon={label.icon}
              interactive={false}
              keyboard={false}
            />
          ))}
          {me && <Marker position={me} icon={youIcon} title={t('map.you')} />}
          <PanTo target={focus} />
        </MapContainer>
        <SeverityLegend className="absolute top-3 left-3 z-[500]" />
      </div>

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
                  ? t(`hazard.${cause.kind}.short` as const, { from: formatClock(cause.window.from) })
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
