import { useState } from 'react'
import { computeArrivals, formatArrival, formatClock, parseClock } from '../../../domain/timing'
import type { Minutes } from '../../../domain/types'
import { useT } from '../../../i18n'
import { formatWeekday } from '../../../lib/format'
import { stopWaypoint } from '../../../lib/route'
import { usePlan, useTurnaround } from '../../../store/plan'
import { AlternativeCard } from '../../AlternativeCard'
import { Disclaimer } from '../../Card'
import { ChoiceGroup } from '../../ChoiceGroup'
import { PACE_OPTIONS } from '../stepMaps'
import type { StepProps } from './types'

function TimeField({ label, value, onChange }: { label: string; value: Minutes; onChange: (m: Minutes) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[13px] text-muted">{label}</span>
      <input
        type="time"
        step={300}
        value={formatClock(value)}
        onChange={(e) => {
          const minutes = parseClock(e.target.value)
          if (minutes !== null) onChange(minutes)
        }}
        className="h-12 w-full rounded-control border-[1.5px] border-line bg-card px-3 text-[15px] font-semibold tabular-nums"
      />
    </label>
  )
}

export function PlanPanel({ view, model }: StepProps) {
  const { t, lang } = useT()
  const date = usePlan((s) => s.date)
  const originalStart = usePlan((s) => s.originalStart)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const groupSize = usePlan((s) => s.groupSize)
  const setStart = usePlan((s) => s.setStart)
  const setTurnaround = usePlan((s) => s.setTurnaround)
  const setPaceAnswer = usePlan((s) => s.setPaceAnswer)
  const setGroupSize = usePlan((s) => s.setGroupSize)
  const turnaround = useTurnaround()
  const [adjusting, setAdjusting] = useState(false)

  const { route, data, evaluation, arrivals, start, paceAnswer } = view
  const crux = stopWaypoint(route, route.cruxStopId)
  const forecastTime = formatClock(data.forecast.issuedAt)

  const startAlt = data.alternatives.find(
    (a) =>
      a.kind === 'startEarlier' && start > a.start && evaluation.flagged.some((f) => f.hazard.id === a.dependsOn),
  )
  const routeAlts = data.alternatives.filter((a) => a.kind === 'altRoute')

  const tiles = [
    { label: t('brief.start'), value: formatClock(start) },
    { label: crux.name, value: formatArrival(arrivals[route.cruxStopId]), warn: arrivals[route.cruxStopId] > turnaround },
    { label: t('brief.backAt'), value: formatArrival(model.end), warn: model.end > route.lastBoat },
  ]

  return (
    <div className="flex flex-col gap-3.5">
      {hikeStarted && (
        <p role="status" className="rounded-card bg-subtle px-4 py-3 text-[13px] leading-normal text-ink-3">
          {t('pre.locked')}
        </p>
      )}

      <section className="flex flex-col gap-3 rounded-crux bg-ink px-5 pt-5 pb-[18px] text-white">
        <p className="text-xs font-semibold tracking-[0.08em] text-crux-label uppercase">{t('brief.ruleEyebrow')}</p>
        <div>
          <h3 className="font-serif text-[26px] leading-[1.15] font-medium text-pretty">
            {t('brief.ruleBig', { place: crux.name, time: formatClock(turnaround) })}
          </h3>
          <p className="mt-1.5 text-[15px] leading-snug text-crux-body">{t('brief.ruleElse', { bailout: route.bailoutName })}</p>
        </div>
        <dl className="flex gap-2">
          {tiles.map((tile) => (
            <div key={tile.label} className="min-w-0 flex-1 rounded-control bg-crux-tile px-3 py-2.5">
              <dt className="truncate text-[11px] text-crux-muted">{tile.label}</dt>
              <dd className={`text-xl font-semibold tabular-nums ${tile.warn ? 'text-crux-warn' : ''}`}>{tile.value}</dd>
            </div>
          ))}
        </dl>
        <p className="text-[13px] leading-normal text-crux-muted">
          {t('brief.ruleWhy', { boat: formatClock(route.lastBoat) })}
        </p>
      </section>

      {paceAnswer === null && (
        <div className="flex flex-col gap-2 rounded-card border-[1.5px] border-plum bg-card p-4">
          <p className="text-[15px] font-semibold">{t('brief.paceQuestion')}</p>
          <ChoiceGroup
            label={t('brief.paceQuestion')}
            options={PACE_OPTIONS.map((value) => ({ value, label: t(`pace.${value}` as const) }))}
            value={paceAnswer}
            onChange={setPaceAnswer}
            disabled={hikeStarted}
          />
          <p className="text-xs text-muted">{t('brief.paceNeeded')}</p>
        </div>
      )}

      {(startAlt || routeAlts.length > 0 || start !== originalStart) && (
        <section className="flex flex-col gap-2">
          <h3 className="px-1 text-[15px] font-semibold">{t('alts.title')}</h3>
          {start !== originalStart && (
            <p role="status" className="px-1 text-[13px] text-plum">
              {t('alts.applied', { start: formatClock(start) })}{' '}
              <button type="button" className="font-semibold underline" onClick={() => setStart(originalStart)} disabled={hikeStarted}>
                {t('brief.undo')}
              </button>
            </p>
          )}
          {startAlt && startAlt.kind === 'startEarlier' && (
            <AlternativeCard
              suggested
              title={t('alt.startEarlier.title', { start: formatClock(startAlt.start) })}
              body={t('alt.startEarlier.body', {
                place: crux.name,
                time: formatArrival(computeArrivals(route, startAlt.start, paceAnswer)[route.cruxStopId]),
                boat: formatClock(route.lastBoat),
              })}
              badge={<span className="shrink-0 text-xs font-semibold text-plum">{t('alts.suggested')}</span>}
              onSelect={hikeStarted ? undefined : () => setStart(startAlt.start)}
            />
          )}
          {routeAlts.map(
            (alt) =>
              alt.kind === 'altRoute' && (
                <AlternativeCard
                  key={alt.id}
                  title={t('alt.bailout.title', { place: alt.place, grade: alt.grade })}
                  body={t('alt.bailout.body', { day: formatWeekday(date, lang), time: forecastTime })}
                  badge={<span className="shrink-0 text-xs text-muted">{alt.duration}</span>}
                />
              ),
          )}
        </section>
      )}

      {!hikeStarted && (
        <div className="flex flex-col gap-3 rounded-card border border-line bg-card p-4">
          <button
            type="button"
            aria-expanded={adjusting}
            onClick={() => setAdjusting((v) => !v)}
            className="flex items-center justify-between text-left text-[15px] font-semibold"
          >
            {t('brief.adjust')}
            <span className="text-[13px] text-plum">{adjusting ? t('pre.adjustClose') : t('pre.adjust')}</span>
          </button>
          {adjusting && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <TimeField label={t('pre.adjustStart')} value={start} onChange={setStart} />
                <TimeField label={t('pre.adjustTurnaround', { place: crux.name })} value={turnaround} onChange={setTurnaround} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-ink-3">{t('pre.groupSize')}</span>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    aria-label={t('common.decrease')}
                    disabled={groupSize <= 2}
                    onClick={() => setGroupSize(groupSize - 1)}
                    className="size-11 rounded-full border-[1.5px] border-line text-lg disabled:opacity-40"
                  >
                    −
                  </button>
                  <span className="w-6 text-center font-semibold tabular-nums" aria-live="polite">
                    {groupSize}
                  </span>
                  <button
                    type="button"
                    aria-label={t('common.increase')}
                    disabled={groupSize >= 12}
                    onClick={() => setGroupSize(groupSize + 1)}
                    className="size-11 rounded-full border-[1.5px] border-line text-lg disabled:opacity-40"
                  >
                    +
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <Disclaimer>{t('disclaimer')}</Disclaimer>
    </div>
  )
}
