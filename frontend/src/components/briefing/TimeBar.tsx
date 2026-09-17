import type { Minutes } from '../../domain/types'
import { formatArrival } from '../../domain/timing'

export interface TimeMark {
  at: Minutes
  label: string
  tone: 'ink' | 'plum' | 'muted'
  /** Above or below the bar, so neighbouring labels don't collide. */
  side: 'top' | 'bottom'
}

interface Props {
  start: Minutes
  end: Minutes
  /** The walker's clock; the bar fills up to here. */
  now: Minutes
  /** Arrivals at each stop, ticked on the bar. */
  stops: Minutes[]
  marks: TimeMark[]
}

const TONE = { ink: 'text-ink', plum: 'text-plum', muted: 'text-muted' }
const LINE = { ink: 'bg-ink', plum: 'bg-plum', muted: 'bg-muted' }

/** The day from first step to last, with the times that matter pinned onto it. */
export function TimeBar({ start, end, now, stops, marks }: Props) {
  const low = Math.min(start, ...marks.map((m) => m.at))
  const high = Math.max(end, ...marks.map((m) => m.at))
  const span = high - low || 1
  const pct = (m: Minutes) => `${((Math.max(low, Math.min(high, m)) - low) / span) * 100}%`
  const fill = ((Math.max(start, Math.min(end, now)) - low) / span) * 100

  // Near either end a centred label would run off the bar; anchor it to that end instead.
  const align = (m: Minutes) => {
    const share = (m - low) / span
    return share > 0.8 ? '-translate-x-full' : share < 0.2 ? '' : '-translate-x-1/2'
  }

  const label = (mark: TimeMark) => (
    <span
      key={`${mark.side}-${mark.label}`}
      className={`absolute text-[11px] leading-tight font-semibold whitespace-nowrap ${align(mark.at)} ${TONE[mark.tone]} ${
        mark.side === 'top' ? 'bottom-0' : 'top-0'
      }`}
      style={{ left: pct(mark.at) }}
    >
      {mark.label}
    </span>
  )

  return (
    <div aria-hidden="true">
      <div className="relative h-5">{marks.filter((m) => m.side === 'top').map(label)}</div>
      <div className="relative my-1.5 h-2.5 rounded-full bg-subtle">
        <div className="absolute inset-y-0 rounded-full bg-ink" style={{ left: pct(start), width: `${Math.max(0, fill - ((start - low) / span) * 100)}%` }} />
        {stops.map((at, i) => (
          <span
            key={i}
            className={`absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full transition-colors duration-300 ${at <= now ? 'bg-white' : 'bg-line'}`}
            style={{ left: pct(at) }}
          />
        ))}
        {marks.map((mark) => (
          <span
            key={`line-${mark.label}`}
            className={`absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full ${LINE[mark.tone]}`}
            style={{ left: pct(mark.at) }}
          />
        ))}
      </div>
      <div className="relative h-5">{marks.filter((m) => m.side === 'bottom').map(label)}</div>
      <div className="mt-1 flex justify-between text-xs text-muted tabular-nums">
        <span>{formatArrival(low)}</span>
        <span>{formatArrival(high)}</span>
      </div>
    </div>
  )
}
