import { formatArrival, formatClock } from '../../../domain/timing'
import { useT } from '../../../i18n'
import { formatDuration } from '../../../lib/format'
import { usePlan, useTurnaround } from '../../../store/plan'
import { ChoiceGroup } from '../../ChoiceGroup'
import { minuteAt, PACE_OPTIONS } from '../stepMaps'
import { TimeBar } from '../TimeBar'
import type { StepProps } from './types'

export function TimePanel({ view, model, progress }: StepProps) {
  const { t } = useT()
  const setPaceAnswer = usePlan((s) => s.setPaceAnswer)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const turnaround = useTurnaround()
  const { route, arrivals, paceAnswer } = view
  const crux = model.keyStops.find((key) => key.role === 'crux')
  const cruxArrival = arrivals[route.cruxStopId]
  const minute = minuteAt(model, progress)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <p className="text-[13px] font-semibold text-ink-3">{t('brief.paceQuestion')}</p>
        <ChoiceGroup
          label={t('brief.paceQuestion')}
          options={PACE_OPTIONS.map((value) => ({ value, label: t(`pace.${value}` as const) }))}
          value={paceAnswer}
          onChange={setPaceAnswer}
          disabled={hikeStarted}
        />
        {!paceAnswer && <p className="text-xs text-muted">{t('brief.paceCautious')}</p>}
      </div>

      <div className="flex items-end justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-[11px] text-muted">{t('brief.start')}</span>
          <span className="text-xl font-semibold tabular-nums">{formatClock(model.start)}</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="font-serif text-[30px] leading-none font-medium tabular-nums">
            {formatDuration((minute - model.start))}
          </span>
          <span className="mt-1 text-[11px] text-muted">{t('brief.breaksIncluded')}</span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[11px] text-muted">{t('brief.backAt')}</span>
          <span className="text-xl font-semibold tabular-nums">{formatArrival(model.end)}</span>
        </div>
      </div>

      <TimeBar
        start={model.start}
        end={model.end}
        now={minute}
        stops={route.stops.map((stop) => arrivals[stop.id])}
        marks={[
          { at: turnaround, label: t('map.turnBy', { time: formatClock(turnaround) }), tone: 'plum', side: 'top' },
          ...(crux ? [{ at: cruxArrival, label: `${crux.name} ${formatArrival(cruxArrival)}`, tone: 'ink' as const, side: 'bottom' as const }] : []),
        ]}
      />

      {progress >= 1 && crux && cruxArrival > turnaround && (
        <p role="status" className="text-[13px] font-semibold text-sev-high">
          {t('brief.lateCrux', { place: crux.name })}
        </p>
      )}
    </div>
  )
}
