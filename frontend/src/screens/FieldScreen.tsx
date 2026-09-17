import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { BottomAction } from '../components/BottomAction'
import { Button, ButtonLink } from '../components/Button'
import { ChevronRight } from '../components/icons'
import { fieldProgress, plannedSnap, trackOf } from '../domain/field'
import { clockOf, computeArrivals, formatClock, turnaroundStatus } from '../domain/timing'
import type { CloudAnswer } from '../domain/types'
import { useT } from '../i18n'
import { useFieldPosition } from '../hooks/useFieldPosition'
import { formatInt, formatKm } from '../lib/format'
import { stopById, stopLabel, stopWaypoint } from '../lib/route'
import { buttonClass } from '../lib/ui'
import { usePlan, useRoute, useTurnaround } from '../store/plan'

const CLOUD_ANSWERS: CloudAnswer[] = ['above', 'touching', 'below']
const PROMPT_TIMEOUT_MS = 2 * 60 * 1000
const CLOCK_TICK_MS = 30 * 1000

/** The wall clock in minutes since midnight, re-read every tick. */
function useClock(): number {
  const [now, setNow] = useState(() => clockOf(new Date()))
  useEffect(() => {
    const id = setInterval(() => setNow(clockOf(new Date())), CLOCK_TICK_MS)
    return () => clearInterval(id)
  }, [])
  return now
}

/** 04: dark, large type, one glance. Where you are on the route, against the rule you set last night. */
export function FieldScreen() {
  const { t, tr, lang } = useT()
  const navigate = useNavigate()
  const route = useRoute()
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const turnaround = useTurnaround()
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const hikeStartedAt = usePlan((s) => s.hikeStartedAt)
  const cloudObservation = usePlan((s) => s.cloudObservation)
  const observeCloud = usePlan((s) => s.observeCloud)
  const endHike = usePlan((s) => s.endHike)
  const [promptOpen, setPromptOpen] = useState(cloudObservation === null)
  const [confirmEnd, setConfirmEnd] = useState(false)
  const now = useClock()
  const track = useMemo(() => trackOf(route), [route])
  const position = useFieldPosition(track, hikeStarted)

  // Prompts dismiss themselves; nothing blocks the screen.
  useEffect(() => {
    if (!promptOpen) return
    const id = setTimeout(() => setPromptOpen(false), PROMPT_TIMEOUT_MS)
    return () => clearTimeout(id)
  }, [promptOpen])

  if (!hikeStarted) {
    return (
      <main className="flex flex-1 flex-col justify-center gap-4 px-[22px] py-12">
        <h1 className="font-serif text-[34px] leading-[1.15] font-medium">{t('field.notStarted')}</h1>
        <p className="text-xl leading-[1.4] text-field-muted">{t('field.notStartedBody')}</p>
        <ButtonLink to="/" className="mt-4">
          {t('field.toPlan')}
        </ButtonLink>
      </main>
    )
  }

  const crux = stopWaypoint(route, route.cruxStopId)
  // Without a fix, where the plan says you'd be by now, timed from when you actually set off.
  const startedAt = hikeStartedAt ? clockOf(new Date(hikeStartedAt)) : now
  const snap = position.snap ?? plannedSnap(track, computeArrivals(route, startedAt, paceAnswer), route, now)
  const progress = fieldProgress(route, track, snap, paceAnswer, now)
  const target = stopById(route, progress.targetStopId)
  const status = progress.passedCrux ? 'ahead' : turnaroundStatus(progress.eta, turnaround)
  const ruleSaysTurn = (!progress.passedCrux && status === 'behind') || cloudObservation?.answer === 'below'
  const positionNote =
    position.status === 'offRoute'
      ? t('field.offRoute')
      : position.status === 'tracking'
        ? null
        : position.status === 'searching' && !position.snap
          ? t('field.searching')
          : position.snap
            ? null
            : t('field.noPosition')

  return (
    <>
      <div className="flex items-center justify-between px-[22px] pt-[max(env(safe-area-inset-top),28px)] text-[13px] text-field-muted">
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="size-2 rounded-full bg-field-muted" />
          {t('field.started', { time: hikeStartedAt ? formatClock(clockOf(new Date(hikeStartedAt))) : '--:--' })}
        </span>
        <span className="tabular-nums">{formatClock(now)}</span>
      </div>

      <main className="flex flex-1 flex-col gap-[18px] px-[22px] pt-[22px] pb-2">
        <div>
          <p className="text-[13px] font-semibold tracking-[0.08em] text-field-muted uppercase">
            {t('field.next', {
              place: stopLabel(target, t),
              km: formatKm(progress.remainingKm, lang),
              ascent: formatInt(progress.remainingAscentM),
            })}
          </p>
          <h1 className="mt-2 font-serif text-[34px] leading-[1.15] font-medium text-pretty">
            {progress.passedCrux ? t('field.pastCrux', { place: crux.name }) : status === 'ahead' ? t('field.ahead') : t('field.behind')}
          </h1>
          <p className="mt-2.5 text-xl leading-[1.4] text-crux-body">
            {progress.passedCrux
              ? tr('field.etaEnd', {
                  place: stopLabel(target, t),
                  eta: <strong className="font-semibold text-white">{formatClock(progress.eta)}</strong>,
                })
              : tr('field.eta', {
                  place: crux.name,
                  eta: <strong className="font-semibold text-white">{formatClock(progress.eta)}</strong>,
                  rule: <strong className="font-semibold text-white">{t('field.turnBy', { time: formatClock(turnaround) })}</strong>,
                })}
          </p>
          {positionNote && (
            <p role="status" className="mt-2 text-[15px] leading-normal text-field-muted">
              {positionNote}
            </p>
          )}
        </div>

        {ruleSaysTurn && (
          <p role="alert" className="rounded-crux border-2 border-sev-high p-[18px] text-xl leading-[1.35] font-semibold">
            {t('field.ruleSaysTurn', { bailout: route.bailoutName })}
          </p>
        )}

        <section className="flex flex-col gap-1.5 rounded-crux bg-field-card p-[18px]">
          <h2 className="text-[13px] text-field-muted">{t('field.decided')}</h2>
          <p className="text-lg leading-[1.4] font-semibold">
            {t('field.rule', { place: crux.name, time: formatClock(turnaround), bailout: route.bailoutName })}
          </p>
        </section>

        {promptOpen ? (
          <section className="flex flex-col gap-3.5 rounded-crux bg-field-card p-[18px]">
            <h2 className="text-lg leading-[1.35] font-semibold">{t('field.prompt')}</h2>
            <div className="flex flex-col gap-2">
              {CLOUD_ANSWERS.map((answer) => (
                <button
                  key={answer}
                  type="button"
                  onClick={() => {
                    observeCloud(answer)
                    setPromptOpen(false)
                  }}
                  className="flex min-h-[52px] items-center rounded-control bg-field-control px-4 py-2 text-left text-[17px] font-medium hover:bg-field-button"
                >
                  {t(`field.cloud.${answer}` as const)}
                </button>
              ))}
            </div>
            <p className="text-[13px] text-field-hint">{t('field.promptHint')}</p>
          </section>
        ) : (
          cloudObservation && (
            <p className="px-1 text-[15px] leading-normal text-field-muted">
              {t('field.noted', {
                time: formatClock(clockOf(new Date(cloudObservation.at))),
                answer: t(`field.cloud.${cloudObservation.answer}` as const),
              })}
            </p>
          )
        )}

        {confirmEnd ? (
          <div role="alertdialog" aria-labelledby="end-hike-title" className="mt-auto flex flex-col gap-3 rounded-crux bg-field-card p-[18px]">
            <p id="end-hike-title" className="text-lg font-semibold">
              {t('field.endConfirm')}
            </p>
            <div className="flex gap-2.5">
              <Button variant="field" size="md" className="flex-1" onClick={() => setConfirmEnd(false)}>
                {t('field.keepGoing')}
              </Button>
              <Button
                size="md"
                className="flex-1"
                onClick={() => {
                  endHike()
                  navigate('/')
                }}
              >
                {t('field.endHike')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-auto flex items-center justify-between gap-3 text-[15px]">
            <Link to="/share" className="flex h-11 items-center gap-1 text-field-muted hover:text-white">
              {t('field.groupCard')}
              <ChevronRight />
            </Link>
            <button type="button" onClick={() => setConfirmEnd(true)} className="h-11 text-field-muted hover:text-white">
              {t('field.endHike')}
            </button>
          </div>
        )}
      </main>

      <BottomAction dark>
        <ButtonLink to="/map" variant="field" className="flex-1">
          {t('field.showDescent')}
        </ButtonLink>
        {/* Opens the dialer; the app never initiates contact itself. */}
        <a href="tel:1414" className={buttonClass('danger', 'lg', 'flex-1')}>
          {t('field.emergency')}
        </a>
      </BottomAction>
    </>
  )
}
