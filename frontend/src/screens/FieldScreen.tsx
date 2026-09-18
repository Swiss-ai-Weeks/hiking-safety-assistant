import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { assessmentQuery } from '../api/queries'
import { AskComposer } from '../components/ask/AskComposer'
import { AskConversation, type AppMessage } from '../components/ask/AskConversation'
import { useAsk } from '../components/ask/useAsk'
import { useBriefingModel } from '../components/briefing/model'
import { RouteMap, type MapPin } from '../components/briefing/RouteMap'
import { Button, ButtonLink } from '../components/Button'
import { LocateIcon, MoreIcon, PhoneIcon } from '../components/icons'
import { evaluate } from '../domain/assessment'
import { fieldProgress, plannedSnap, trackOf } from '../domain/field'
import { pathUpTo, pointAlong } from '../domain/geometry'
import { clockOf, computeArrivals, formatClock, turnaroundStatus } from '../domain/timing'
import type { CloudAnswer, LatLng } from '../domain/types'
import { useT } from '../i18n'
import { useFieldPosition } from '../hooks/useFieldPosition'
import { formatInt, formatKm } from '../lib/format'
import { stopById, stopLabel, stopWaypoint } from '../lib/route'
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

type Sheet = 'peek' | 'open'

/**
 * 04: on the trail. The map is the screen: where you are, what is ahead and how it is coloured. Over it,
 * one status line and the rule when it says turn. Below, three numbers, and a conversation with the
 * model that you can always type into. The app's own check-ins sit in the same thread, unbadged.
 */
export function FieldScreen() {
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const { t } = useT()

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
  return <ActiveHike />
}

function ActiveHike() {
  const { t, lang } = useT()
  const navigate = useNavigate()
  const route = useRoute()
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const date = usePlan((s) => s.date)
  const turnaround = useTurnaround()
  const hikeStartedAt = usePlan((s) => s.hikeStartedAt)
  const cloudObservation = usePlan((s) => s.cloudObservation)
  const observeCloud = usePlan((s) => s.observeCloud)
  const endHike = usePlan((s) => s.endHike)
  const now = useClock()

  const [promptOpen, setPromptOpen] = useState(cloudObservation === null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmEnd, setConfirmEnd] = useState(false)
  const [sheet, setSheet] = useState<Sheet>('peek')
  const [following, setFollowing] = useState(true)
  const [recentre, setRecentre] = useState(0)

  const track = useMemo(() => trackOf(route), [route])
  const position = useFieldPosition(track, true)
  const startedAt = hikeStartedAt ? clockOf(new Date(hikeStartedAt)) : now
  const arrivals = useMemo(() => computeArrivals(route, startedAt, paceAnswer), [route, startedAt, paceAnswer])
  const model = useBriefingModel({ route, arrivals, start: startedAt })

  // Not suspended: out on the trail the map and the numbers must show even when the server does not.
  const assessment = useQuery(assessmentQuery(route.id, date)).data
  const evaluation = useMemo(() => (assessment ? evaluate(route, arrivals, assessment) : null), [route, arrivals, assessment])

  // Without a fix, where the plan says you'd be by now, timed from when you actually set off.
  const snap = position.snap ?? plannedSnap(track, arrivals, route, now)
  const progress = fieldProgress(route, track, snap, paceAnswer, now)
  const target = stopById(route, progress.targetStopId)
  const crux = stopWaypoint(route, route.cruxStopId)
  const status = progress.passedCrux ? 'pastCrux' : turnaroundStatus(progress.eta, turnaround)
  const ruleSaysTurn = status === 'behind' || cloudObservation?.answer === 'below'

  const walker = useMemo(() => pointAlong(track, snap.progressM)?.latLng ?? null, [track, snap.progressM])
  const trail = useMemo(() => pathUpTo(track, snap.progressM), [track, snap.progressM])
  // A new array only when the walker moves or the hiker asks to recentre: `PanTo` pans on every new one.
  const focus = useMemo<LatLng | null>(
    () => (following && walker ? [walker[0], walker[1]] : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [following, walker, recentre],
  )

  const pins: MapPin[] = model.keyStops
    .filter((key) => key.role !== 'start')
    .map((key) => ({
      key: `field-${key.stop.waypointId}`,
      latLng: key.latLng,
      below: key.role === 'crux',
      text:
        key.role === 'crux'
          ? `${key.name} · ${t('map.turnBy', { time: formatClock(turnaround) })}`
          : key.role === 'bailout'
            ? `${key.name} · ${t('map.bailout')}`
            : key.name,
      variant: key.role === 'crux' ? 'crux' : key.role === 'bailout' ? 'turn' : '',
    }))

  // Prompts dismiss themselves; nothing blocks the screen.
  useEffect(() => {
    if (!promptOpen) return
    const id = setTimeout(() => setPromptOpen(false), PROMPT_TIMEOUT_MS)
    return () => clearTimeout(id)
  }, [promptOpen])

  const ask = useAsk({
    route,
    context: () => ({
      plan: { start: startedAt, turnaround, arrivals },
      live: {
        now: clockOf(new Date()),
        status,
        nextStopId: progress.targetStopId,
        eta: Math.round(progress.eta),
        remainingKm: Math.round(progress.remainingKm * 10) / 10,
        remainingAscentM: Math.round(progress.remainingAscentM),
        offRoute: position.status === 'offRoute',
        cloud: cloudObservation?.answer ?? null,
      },
    }),
  })

  const appMessages: AppMessage[] = [
    {
      id: 'plan',
      at: hikeStartedAt ?? 0,
      eyebrow: t('field.yourPlan'),
      body: t('field.rule', { place: crux.name, time: formatClock(turnaround), bailout: route.bailoutName }),
    },
  ]
  if (cloudObservation) {
    appMessages.push({
      id: `cloud-${cloudObservation.at}`,
      at: cloudObservation.at,
      eyebrow: t('field.checkIn'),
      body: t('field.noted', {
        time: formatClock(clockOf(new Date(cloudObservation.at))),
        answer: t(`field.cloud.${cloudObservation.answer}` as const),
      }),
    })
  }
  if (ruleSaysTurn) {
    appMessages.push({
      id: 'turn',
      // The current minute, read off the clock this screen already ticks: the rule stays the latest word.
      at: (hikeStartedAt ?? 0) + (now - startedAt) * 60_000,
      eyebrow: t('field.ruleEyebrow'),
      body: t('field.ruleSaysTurn', { bailout: route.bailoutName }),
      tone: 'alert',
    })
  }

  const statusText =
    status === 'pastCrux'
      ? t('field.status.pastCrux', { place: crux.name })
      : status === 'behind'
        ? t('field.status.behind')
        : t('field.status.ahead', { time: formatClock(turnaround) })
  const positionNote =
    position.status === 'offRoute'
      ? t('field.position.offRoute')
      : position.status === 'tracking' || position.snap
        ? null
        : position.status === 'searching'
          ? t('field.position.searching')
          : t('field.position.noPosition')

  const send = (question: string) => {
    setSheet('open')
    void ask.send(question)
  }

  // Dragging the handle: up opens the conversation, down lowers it. A tap toggles.
  const dragFrom = useRef<number | null>(null)
  const onHandleDown = (event: PointerEvent) => {
    dragFrom.current = event.clientY
  }
  const onHandleUp = (event: PointerEvent) => {
    const from = dragFrom.current
    dragFrom.current = null
    if (from === null) return
    const dy = event.clientY - from
    if (dy < -24) setSheet('open')
    else if (dy > 24) setSheet('peek')
    else setSheet((current) => (current === 'open' ? 'peek' : 'open'))
  }

  return (
    <div className="relative h-dvh overflow-hidden bg-field">
      <div className="absolute inset-0">
        <RouteMap
          route={route}
          className="h-full w-full"
          legPaint={evaluation ? evaluation.legSeverity : 'plain'}
          pins={pins}
          walker={walker}
          me={position.status === 'offRoute' ? position.fix : null}
          trail={trail}
          focus={focus}
          padTop={140}
          padBottom={promptOpen ? 380 : 260}
          onUserPan={() => setFollowing(false)}
        />
      </div>

      {/* Over the map: status, clock, menu; the rule when it says turn; where the position comes from. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1000] flex flex-col gap-2 px-3 pt-[max(env(safe-area-inset-top),12px)]">
        <div className="flex items-center gap-2">
          <p
            role="status"
            className="pointer-events-auto flex min-w-0 items-center gap-2 rounded-full bg-field/90 px-3.5 py-2 text-[15px] font-semibold shadow-lg backdrop-blur"
          >
            <span
              aria-hidden="true"
              className={`size-2.5 shrink-0 rounded-full ${status === 'behind' ? 'bg-sev-high' : status === 'pastCrux' ? 'bg-field-muted' : 'bg-white'}`}
            />
            <span className="truncate">{statusText}</span>
          </p>
          <span className="ml-auto rounded-full bg-field/90 px-3 py-2 text-[15px] font-semibold tabular-nums shadow-lg backdrop-blur">
            {formatClock(now)}
          </span>
          <button
            type="button"
            aria-label={t('field.menu')}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="pointer-events-auto flex size-10 items-center justify-center rounded-full bg-field/90 shadow-lg backdrop-blur"
          >
            <MoreIcon />
          </button>
        </div>
        {ruleSaysTurn && (
          <p role="alert" className="rounded-2xl bg-sev-high px-4 py-3 text-[17px] leading-snug font-semibold shadow-lg">
            {t('field.ruleSaysTurn', { bailout: route.bailoutName })}
          </p>
        )}
        {positionNote && (
          <p className="self-start rounded-full bg-field/85 px-3 py-1 text-xs text-field-muted backdrop-blur">
            {t('field.started', { time: formatClock(startedAt) })} · {positionNote}
          </p>
        )}
        {menuOpen && (
          <nav className="pointer-events-auto flex flex-col self-end overflow-hidden rounded-2xl bg-field-card text-[15px] shadow-xl">
            <Link to="/map" className="px-4 py-3 text-white no-underline hover:bg-field-button hover:text-white">
              {t('field.fullMap')}
            </Link>
            <Link to="/share" className="px-4 py-3 text-white no-underline hover:bg-field-button hover:text-white">
              {t('field.groupCard')}
            </Link>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false)
                setConfirmEnd(true)
              }}
              className="px-4 py-3 text-left text-sev-high hover:bg-field-button"
            >
              {t('field.endHike')}
            </button>
          </nav>
        )}
      </div>

      <section
        className={`absolute inset-x-0 bottom-0 z-[1000] flex flex-col rounded-t-sheet bg-field shadow-[0_-8px_24px_rgba(0,0,0,0.35)] ${
          sheet === 'open' ? 'h-[66dvh]' : ''
        }`}
      >
        {/* Floating over the map's lower edge: recentre and SOS, always reachable. */}
        <div className="pointer-events-none absolute inset-x-3 -top-[68px] flex items-end justify-between">
          {!following ? (
            <button
              type="button"
              onClick={() => {
                setFollowing(true)
                setRecentre((n) => n + 1)
              }}
              className="pointer-events-auto flex h-11 items-center gap-1.5 rounded-full bg-field/90 px-3.5 text-sm font-semibold shadow-lg backdrop-blur"
            >
              <LocateIcon className="size-4" />
              {t('field.recenter')}
            </button>
          ) : (
            <span />
          )}
          {/* Opens the dialer; the app never initiates contact itself. */}
          <a
            href="tel:1414"
            aria-label={t('field.emergency')}
            className="pointer-events-auto flex size-14 flex-col items-center justify-center rounded-full bg-sev-high text-white no-underline shadow-xl hover:text-white"
          >
            <PhoneIcon className="size-5" />
            <span className="text-[10px] leading-none font-bold">{t('field.sos')}</span>
          </a>
        </div>

        <button
          type="button"
          aria-label={sheet === 'open' ? t('field.hideConversation') : t('field.showConversation')}
          aria-expanded={sheet === 'open'}
          onPointerDown={onHandleDown}
          onPointerUp={onHandleUp}
          className="flex h-6 w-full shrink-0 touch-none items-center justify-center"
        >
          <span aria-hidden="true" className="h-1 w-10 rounded-full bg-field-button" />
        </button>

        <dl className="grid shrink-0 grid-cols-3 gap-2 px-4 pb-3">
          <div className="min-w-0">
            <dt className="text-[11px] font-semibold tracking-[0.08em] text-field-muted uppercase">{t('field.statNext')}</dt>
            <dd className="truncate text-[17px] font-semibold">{stopLabel(target, t)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-[11px] font-semibold tracking-[0.08em] text-field-muted uppercase">{t('field.statLeft')}</dt>
            <dd className="text-[17px] font-semibold tabular-nums">
              {formatKm(progress.remainingKm, lang)} km <span className="text-field-muted">↑{formatInt(progress.remainingAscentM)}</span>
            </dd>
          </div>
          <div className="min-w-0 text-right">
            <dt className="text-[11px] font-semibold tracking-[0.08em] text-field-muted uppercase">{t('field.statEta')}</dt>
            <dd className={`text-[17px] font-semibold tabular-nums ${status === 'behind' ? 'text-sev-high' : ''}`}>
              {formatClock(progress.eta)}
            </dd>
          </div>
        </dl>

        {sheet === 'open' && (
          <div className="min-h-0 flex-1 overflow-y-auto border-t border-white/10 px-4 pt-3 pb-2">
            <AskConversation
              ask={ask}
              dark
              appMessages={appMessages}
              suggestions={[
                t('ask.suggest.field.next', { next: stopLabel(target, t) }),
                t('ask.suggest.field.weather', { crux: crux.name }),
                t('ask.suggest.field.cloud'),
              ]}
            />
          </div>
        )}

        {promptOpen && sheet === 'peek' && (
          <div className="shrink-0 border-t border-white/10 px-4 py-2.5">
            <p className="text-[13px] font-semibold text-field-muted">{t('field.prompt')}</p>
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {CLOUD_ANSWERS.map((answer) => (
                <button
                  key={answer}
                  type="button"
                  onClick={() => {
                    observeCloud(answer)
                    setPromptOpen(false)
                    // Cloud below the ridge is the rule saying turn: bring the thread up with it.
                    if (answer === 'below') setSheet('open')
                  }}
                  className={`min-h-11 rounded-control px-2 text-[13px] leading-tight font-semibold ${
                    answer === 'below' ? 'bg-sev-high/25 text-white hover:bg-sev-high/40' : 'bg-field-control hover:bg-field-button'
                  }`}
                >
                  {t(`field.cloud.${answer}` as const)}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="shrink-0 px-3 pt-2 pb-[max(env(safe-area-inset-bottom),12px)]">
          <AskComposer
            dark
            pending={ask.pending}
            onSend={send}
            onFocus={() => setSheet('open')}
            placeholder={t('ask.placeholderField')}
          />
        </div>
      </section>

      {confirmEnd && (
        <div className="absolute inset-0 z-[1100] flex items-end bg-black/50 p-3" onClick={() => setConfirmEnd(false)}>
          <div
            role="alertdialog"
            aria-labelledby="end-hike-title"
            onClick={(event) => event.stopPropagation()}
            className="flex w-full flex-col gap-3 rounded-crux bg-field-card p-[18px] pb-[max(env(safe-area-inset-bottom),18px)]"
          >
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
        </div>
      )}
    </div>
  )
}
