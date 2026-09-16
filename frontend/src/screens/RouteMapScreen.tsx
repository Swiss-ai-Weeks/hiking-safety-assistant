import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet'
import { PillButton } from '../components/Button'
import { ChevronRight } from '../components/icons'
import { ScreenHeader } from '../components/ScreenHeader'
import { SeverityDot, SeverityLegend } from '../components/Severity'
import { formatArrival, formatClock } from '../domain/timing'
import type { LatLng, Leg, Route } from '../domain/types'
import { useAssessmentView } from '../hooks/useAssessmentView'
import { useT } from '../i18n'
import { formatInt, formatKm } from '../lib/format'
import { routeName, stopWaypoint, waypointById } from '../lib/route'
import { SEVERITY_STROKE } from '../lib/ui'
import { useTurnaround } from '../store/plan'

/**
 * Where a label sits relative to its dot. The spec's prototype hard-coded one offset per
 * Oeschinensee waypoint, which no computed route has. Instead the label is pushed *away* from the
 * middle of the route, so it leans out over empty map rather than back across the line.
 */
function labelOffset(point: LatLng, centre: LatLng): string {
  const vertical = point[0] >= centre[0] ? 'bottom:12px' : 'top:14px'
  const horizontal = point[1] >= centre[1] ? 'left:-6px' : 'right:-6px'
  return `${horizontal};${vertical}`
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

/**
 * The line to draw for a leg. A computed route carries its real geometry and each leg indexes
 * into it; the demo route has waypoints only, so it falls back to a chord between the two stops.
 */
function legPositions(route: Route, leg: Leg): LatLng[] {
  const { geometry } = route
  if (geometry && leg.fromIndex !== undefined && leg.toIndex !== undefined) {
    return geometry.slice(leg.fromIndex, leg.toIndex + 1)
  }
  return [stopWaypoint(route, leg.fromStop).latLng, stopWaypoint(route, leg.toStop).latLng]
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

  // Fit the real line where there is one: a computed route wanders well outside the box its
  // five waypoints describe.
  const bounds = useMemo(
    () => L.latLngBounds(route.geometry?.length ? route.geometry : route.waypoints.map((w) => w.latLng)),
    [route],
  )
  const forecastTime = formatClock(data.forecast.issuedAt)
  const backTo = params.get('from') === 'field' ? '/field' : { pathname: '/assessment', search }

  /**
   * The four points worth naming on the map, derived from the route rather than listed by id:
   * where you start, where you can still turn back, the crux, and where you are going.
   */
  const labels = useMemo(() => {
    const centre = bounds.getCenter()
    const middle: LatLng = [centre.lat, centre.lng]
    const start = route.stops[0]
    // The turnaround is where the break is taken; failing that, the midpoint of an out-and-back.
    const turnaroundStop =
      route.stops.find((stop) => stop.breakMinutes) ?? route.stops[Math.floor((route.stops.length - 1) / 2)]
    // A computed route names the bail-out stop outright. The demo route gives only a name, so it
    // is matched back to the waypoint that carries it.
    const bailoutStopId =
      route.bailoutStopId ??
      route.stops.find((stop) => waypointById(route, stop.waypointId).name === route.bailoutName)?.id

    const entries: { stopId: string; text: string; variant: '' | 'crux' | 'turn' }[] = [
      { stopId: start.id, text: `${route.fromName} · ${formatArrival(arrivals[start.id])}`, variant: '' },
    ]
    if (bailoutStopId && bailoutStopId !== route.cruxStopId) {
      entries.push({
        stopId: bailoutStopId,
        text: `${route.bailoutName} · ${formatArrival(arrivals[bailoutStopId])} · ${t('map.bailout')}`,
        variant: 'turn',
      })
    }
    const crux = stopWaypoint(route, route.cruxStopId)
    entries.push({
      stopId: route.cruxStopId,
      text: `${crux.name} ${formatInt(crux.elevationM)} m · ${formatArrival(arrivals[route.cruxStopId])} · ${t('map.turnBy', { time: formatClock(turnaround) })}`,
      variant: 'crux',
    })
    if (turnaroundStop.id !== route.cruxStopId) {
      entries.push({ stopId: turnaroundStop.id, text: route.toName, variant: '' })
    }

    return entries.map((entry) => {
      const position = stopWaypoint(route, entry.stopId).latLng
      return { stopId: entry.stopId, position, icon: labelIcon(entry.text, entry.variant, labelOffset(position, middle)) }
    })
  }, [route, arrivals, turnaround, t, bounds])

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
            const positions = legPositions(route, leg)
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
              key={`${label.stopId}-label`}
              position={label.position}
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
