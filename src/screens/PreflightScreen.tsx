import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { BottomAction } from '../components/BottomAction'
import { Button, ButtonLink } from '../components/Button'
import { ChoiceGroup } from '../components/ChoiceGroup'
import { ScreenHeader } from '../components/ScreenHeader'
import { StepCard } from '../components/StepCard'
import { computeArrivals, formatArrival, formatClock, parseClock } from '../domain/timing'
import type { PaceAnswer } from '../domain/types'
import { useT } from '../i18n'
import { stopWaypoint } from '../lib/route'
import { usePlan, useRoute } from '../store/plan'

const PACE_OPTIONS: PaceAnswer[] = ['under5', '5to6', 'over7']

export function PreflightScreen() {
  const { t, tr } = useT()
  const navigate = useNavigate()
  const route = useRoute()
  const start = usePlan((s) => s.start)
  const originalStart = usePlan((s) => s.originalStart)
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const planAccepted = usePlan((s) => s.planAccepted)
  const turnaround = usePlan((s) => s.turnaround)
  const groupSize = usePlan((s) => s.groupSize)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const setPaceAnswer = usePlan((s) => s.setPaceAnswer)
  const acceptPlan = usePlan((s) => s.acceptPlan)
  const setStart = usePlan((s) => s.setStart)
  const setTurnaround = usePlan((s) => s.setTurnaround)
  const setGroupSize = usePlan((s) => s.setGroupSize)
  const startHike = usePlan((s) => s.startHike)
  const [adjusting, setAdjusting] = useState(false)
  const [groupOpen, setGroupOpen] = useState(false)

  const arrivals = useMemo(() => computeArrivals(route, start, paceAnswer), [route, start, paceAnswer])
  const crux = stopWaypoint(route, route.cruxStopId)
  const done = Number(paceAnswer !== null) + Number(planAccepted) + Number(hikeStarted)
  const canStart = paceAnswer !== null && planAccepted && !hikeStarted
  const lastStopId = route.stops[route.stops.length - 1].id

  const onStart = () => {
    startHike()
    // Location is requested only here, with the reason stated in step 3.
    navigator.geolocation?.getCurrentPosition(
      () => {},
      () => {},
      { timeout: 10_000, maximumAge: 60_000 },
    )
    navigate('/field')
  }

  const timeInput = (value: number, onChange: (m: number) => void, label: string) => (
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

  return (
    <>
      <ScreenHeader backTo="/assessment" title={t('pre.title')} subtitle={t('pre.progress', { done })} />

      <main className="flex flex-1 flex-col gap-3.5 px-[18px] pt-[18px] pb-2">
        {hikeStarted && (
          <p role="status" className="rounded-card bg-subtle px-4 py-3 text-[13px] leading-normal text-ink-3">
            {t('pre.locked')} <Link to="/field">{t('pre.toField')}</Link>
          </p>
        )}

        <StepCard step={1} done={paceAnswer !== null} title={t('pre.q1')}>
          <p className="text-[13px] leading-normal text-muted">{t('pre.q1Hint')}</p>
          <ChoiceGroup
            label={t('pre.q1')}
            options={PACE_OPTIONS.map((value) => ({ value, label: t(`pace.${value}` as const) }))}
            value={paceAnswer}
            onChange={setPaceAnswer}
            disabled={hikeStarted}
          />
          {paceAnswer && (
            <p role="status" className="border-t border-divider pt-2.5 text-[13px] leading-normal text-ink-3">
              {t('pre.recomputed', {
                place: crux.name,
                crux: formatArrival(arrivals[route.cruxStopId]),
                end: formatArrival(arrivals[lastStopId]),
              })}
            </p>
          )}
        </StepCard>

        <StepCard step={2} done={planAccepted} title={t('pre.q2')}>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between gap-3 rounded-control bg-subtle px-3.5 py-3">
              <span className="text-sm text-muted">{t('pre.startRow')}</span>
              <span className="text-right text-[15px] font-semibold tabular-nums">
                {formatClock(start)}{' '}
                {start !== originalStart && (
                  <span className="font-normal text-muted">{t('pre.movedFrom', { time: formatClock(originalStart) })}</span>
                )}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-control bg-subtle px-3.5 py-3">
              <span className="text-sm text-muted">{t('pre.turnaroundRow')}</span>
              <p className="text-[15px] leading-[1.4] font-semibold">
                {tr('pre.turnaroundRule', {
                  place: crux.name,
                  time: <span className="text-plum">{formatClock(turnaround)}</span>,
                  bailout: route.bailoutName,
                })}
              </p>
            </div>
            <div className="flex flex-col gap-1 rounded-control bg-subtle px-3.5 py-3">
              <span className="text-sm text-muted">{t('pre.whyRow')}</span>
              <p className="text-sm leading-normal text-ink-2">
                {t('pre.why', { boat: formatClock(route.lastBoat), time: formatClock(turnaround) })}
              </p>
            </div>
          </div>

          {adjusting && !hikeStarted && (
            <div className="grid grid-cols-2 gap-2">
              {timeInput(start, setStart, t('pre.adjustStart'))}
              {timeInput(turnaround, setTurnaround, t('pre.adjustTurnaround', { place: crux.name }))}
            </div>
          )}

          <div className="flex gap-2">
            <Button
              variant={planAccepted ? 'accent' : 'primary'}
              size="md"
              className="flex-1"
              onClick={acceptPlan}
              disabled={hikeStarted}
            >
              {planAccepted ? `✓ ${t('pre.accepted')}` : t('pre.accept')}
            </Button>
            <Button
              variant="secondary"
              size="md"
              className="min-w-24"
              aria-expanded={adjusting}
              onClick={() => setAdjusting((v) => !v)}
              disabled={hikeStarted}
            >
              {adjusting ? t('pre.adjustClose') : t('pre.adjust')}
            </Button>
          </div>
        </StepCard>

        <StepCard step={3} done={hikeStarted} title={t('pre.q3')} dimmed={!canStart && !hikeStarted}>
          <p className="text-[13px] leading-normal text-muted">{t('pre.q3Body')}</p>
        </StepCard>

        <p className="px-1 pt-0.5 text-xs leading-normal text-muted">
          {t('pre.group')}{' '}
          <button
            type="button"
            aria-expanded={groupOpen}
            onClick={() => setGroupOpen((v) => !v)}
            className="text-plum hover:underline"
          >
            {t('pre.changeGroup')}
          </button>
        </p>
        {groupOpen && (
          <div className="flex items-center justify-between rounded-card border border-line bg-card px-4 py-2">
            <span className="text-sm text-ink-3">{t('pre.groupSize')}</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label={t('common.decrease')}
                disabled={hikeStarted || groupSize <= 2}
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
                disabled={hikeStarted || groupSize >= 12}
                onClick={() => setGroupSize(groupSize + 1)}
                className="size-11 rounded-full border-[1.5px] border-line text-lg disabled:opacity-40"
              >
                +
              </button>
            </div>
          </div>
        )}
      </main>

      <BottomAction>
        {hikeStarted ? (
          <ButtonLink to="/field" className="flex-1">
            {t('pre.toField')}
          </ButtonLink>
        ) : (
          <Button className="flex-1" onClick={onStart} disabled={!canStart}>
            {t('pre.cta')}
          </Button>
        )}
      </BottomAction>
    </>
  )
}
