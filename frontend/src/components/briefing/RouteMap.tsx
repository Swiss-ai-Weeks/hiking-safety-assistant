import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Fragment, useEffect, useMemo, type ReactNode } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet'
import type { LatLng, Leg, Route, StopSeverity } from '../../domain/types'
import { stopWaypoint } from '../../lib/route'
import { SEVERITY_STROKE } from '../../lib/ui'

/** How a leg is drawn: by its severity, or in ink while nothing has been checked yet. */
export type LegPaint = StopSeverity | 'plain'

export type PinVariant = '' | 'crux' | 'turn' | 'weather' | 'warn'

export interface MapPin {
  key: string
  latLng: LatLng
  text: string
  variant?: PinVariant
  /** Hang the label under the dot rather than over it. */
  below?: boolean
}

const PLAIN_STROKE = '#2b2723'

/**
 * Where a label sits relative to its dot. It grows *towards* the middle horizontally, so a label at
 * the edge of the route stays on screen, and above or below as the pin asks, so neighbouring
 * points (a crux next to its hut) don't stack their labels.
 */
function labelOffset(point: LatLng, centre: LatLng, below: boolean): string {
  const vertical = below ? 'top:14px' : 'bottom:12px'
  const horizontal = point[1] >= centre[1] ? 'right:-6px' : 'left:-6px'
  return `${horizontal};${vertical}`
}

const dotIcon = L.divIcon({ className: '', html: '<div class="map-dot"></div>', iconSize: [12, 12], iconAnchor: [6, 6] })
const walkerIcon = L.divIcon({ className: '', html: '<div class="map-walker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] })
const youIcon = L.divIcon({
  className: '',
  html: '<div class="map-dot" style="border-color:oklch(0.5 0.12 300)"></div>',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
})

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

/**
 * Label icons, kept by content. Pins are recomputed every animation frame; a new icon would make
 * Leaflet replace the element and replay its pop-in each time.
 */
const labelIcons = new Map<string, L.DivIcon>()
function labelIcon(text: string, variant: PinVariant, position: string): L.DivIcon {
  const key = `${variant}|${position}|${text}`
  let icon = labelIcons.get(key)
  if (!icon) {
    if (labelIcons.size > 300) labelIcons.clear()
    const className = `map-label map-label--pop${variant ? ` map-label--${variant}` : ''}`
    const html = `<div class="${className}" style="${position}">${escapeHtml(text)}</div>`
    icon = L.divIcon({ className: '', html, iconSize: [0, 0], iconAnchor: [0, 0] })
    labelIcons.set(key, icon)
  }
  return icon
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

function PanTo({ target }: { target: LatLng | null | undefined }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.panTo(target, { animate: true })
  }, [map, target])
  return null
}

interface Props {
  route: Route
  /** Legs by paint. `'plain'` for all of them draws the route in ink. */
  legPaint: Record<string, LegPaint> | 'plain'
  /** While set, only this much of the line is drawn, over a faint outline of the rest. */
  drawnPath?: LatLng[] | null
  pins?: MapPin[]
  walker?: LatLng | null
  me?: LatLng | null
  focus?: LatLng | null
  /** Extra room at the bottom of the fitted bounds, for an overlay. */
  padBottom?: number
  onTap?: () => void
  children?: ReactNode
  className?: string
}

export function RouteMap({
  route,
  legPaint,
  drawnPath = null,
  pins = [],
  walker = null,
  me = null,
  focus = null,
  padBottom = 24,
  onTap,
  children,
  className = '',
}: Props) {
  // Fit the real line where there is one: a computed route wanders well outside its waypoints' box.
  const bounds = useMemo(
    () => L.latLngBounds(route.geometry?.length ? route.geometry : route.waypoints.map((w) => w.latLng)),
    [route],
  )
  const centre = useMemo<LatLng>(() => {
    const c = bounds.getCenter()
    return [c.lat, c.lng]
  }, [bounds])

  return (
    <div className={`relative isolate ${className}`} onClick={onTap}>
      <MapContainer
        bounds={bounds}
        boundsOptions={{ paddingTopLeft: [40, 48], paddingBottomRight: [40, padBottom] }}
        zoomControl={false}
        attributionControl
        className="route-map absolute inset-0 h-full w-full"
      >
        {/* swisstopo's national map: contours, rock and marked trails, which OSM tiles draw thinly. */}
        <TileLayer
          url="https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg"
          attribution='&copy; <a href="https://www.swisstopo.admin.ch/">swisstopo</a>'
          maxZoom={18}
        />
        {route.legs.map((leg) => {
          const positions = legPositions(route, leg)
          if (drawnPath) {
            return (
              <Polyline
                key={leg.id}
                positions={positions}
                pathOptions={{ color: PLAIN_STROKE, weight: 3, opacity: 0.25, dashArray: '2 7' }}
              />
            )
          }
          const paint = legPaint === 'plain' ? 'plain' : legPaint[leg.id]
          return (
            <Fragment key={leg.id}>
              <Polyline positions={positions} pathOptions={{ color: '#fff', weight: 9, opacity: 0.9 }} />
              <Polyline
                positions={positions}
                pathOptions={{
                  color: paint === 'plain' ? PLAIN_STROKE : SEVERITY_STROKE[paint],
                  weight: paint === 'high' || paint === 'mod' ? 6 : 5,
                  dashArray: paint === 'unknown' ? '6 8' : undefined,
                }}
              />
            </Fragment>
          )
        })}
        {drawnPath && drawnPath.length > 1 && (
          <>
            <Polyline positions={drawnPath} pathOptions={{ color: '#fff', weight: 9, opacity: 0.9 }} />
            <Polyline positions={drawnPath} pathOptions={{ color: PLAIN_STROKE, weight: 5 }} />
          </>
        )}
        {route.waypoints.map((w) => (
          <Marker key={w.id} position={w.latLng} icon={dotIcon} interactive={false} keyboard={false} />
        ))}
        {pins.map((pin) => (
          <Marker
            key={pin.key}
            position={pin.latLng}
            icon={labelIcon(pin.text, pin.variant ?? '', labelOffset(pin.latLng, centre, pin.below ?? false))}
            interactive={false}
            keyboard={false}
          />
        ))}
        {walker && <Marker position={walker} icon={walkerIcon} interactive={false} keyboard={false} zIndexOffset={1000} />}
        {me && <Marker position={me} icon={youIcon} />}
        <PanTo target={focus} />
      </MapContainer>
      {children}
    </div>
  )
}
