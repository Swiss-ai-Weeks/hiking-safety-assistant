import { useId, useMemo } from 'react'
import type { ProfilePoint } from '../../domain/geometry'
import { formatInt } from '../../lib/format'

const W = 320
const H = 76
const PAD_TOP = 14
const PAD_BOTTOM = 4

interface Props {
  profile: ProfilePoint[]
  lengthM: number
  /** How far along the walker is; the line is inked up to here. */
  alongM: number
  /** Stops to tick on the axis, e.g. the crux. */
  marks?: { alongM: number; label: string }[]
}

/** Height against distance for the whole day, out and back, inked as the walker goes. */
export function ElevationProfile({ profile, lengthM, alongM, marks = [] }: Props) {
  const clipId = useId()
  const shape = useMemo(() => {
    if (profile.length < 2 || lengthM === 0) return null
    const elevations = profile.map((p) => p.elevationM)
    const low = Math.min(...elevations)
    const high = Math.max(...elevations)
    const span = high - low || 1
    const x = (m: number) => (m / lengthM) * W
    const y = (e: number) => PAD_TOP + (1 - (e - low) / span) * (H - PAD_TOP - PAD_BOTTOM)
    const line = profile.map((p, i) => `${i ? 'L' : 'M'}${x(p.alongM).toFixed(1)},${y(p.elevationM).toFixed(1)}`).join('')
    return { line, area: `${line}L${W},${H}L0,${H}Z`, x, y, low, high }
  }, [profile, lengthM])

  if (!shape) return null
  const clamped = Math.max(0, Math.min(lengthM, alongM))
  const walkerX = shape.x(clamped)
  // Between the two samples either side, so the dot glides up and down rather than stepping.
  const at = (clamped / lengthM) * (profile.length - 1)
  const i = Math.min(profile.length - 2, Math.floor(at))
  const walkerElevationM = profile[i].elevationM + (at - i) * (profile[i + 1].elevationM - profile[i].elevationM)

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full overflow-visible" aria-hidden="true">
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={walkerX} height={H} />
          </clipPath>
        </defs>
        <path d={shape.area} className="fill-subtle" />
        <path d={shape.line} fill="none" className="stroke-line" strokeWidth="2" />
        <g clipPath={`url(#${clipId})`}>
          <path d={shape.area} className="fill-plum/10" />
          <path d={shape.line} fill="none" className="stroke-ink" strokeWidth="2.2" strokeLinejoin="round" />
        </g>
        {marks.map((mark) => (
          <line
            key={mark.label}
            x1={shape.x(mark.alongM)}
            x2={shape.x(mark.alongM)}
            y1={PAD_TOP - 6}
            y2={H}
            className="stroke-ink-3"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
        ))}
        <circle cx={walkerX} cy={shape.y(walkerElevationM)} r="5" className="fill-plum stroke-white" strokeWidth="2" />
      </svg>
      {marks.map((mark) => (
        <span
          key={mark.label}
          className="absolute top-0 -translate-x-1/2 text-[11px] font-semibold whitespace-nowrap text-ink"
          style={{ left: `${(mark.alongM / lengthM) * 100}%` }}
        >
          {mark.label}
        </span>
      ))}
      <div className="mt-1 flex justify-between text-[11px] text-muted tabular-nums">
        <span>{formatInt(shape.low)} m</span>
        <span className="font-semibold">↑ {formatInt(shape.high)} m</span>
      </div>
    </div>
  )
}
