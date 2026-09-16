import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { AlternativeCard } from '../components/AlternativeCard'
import { BottomAction } from '../components/BottomAction'
import { Button, PillLink } from '../components/Button'
import { Card, Disclaimer, SectionTitle, Skeleton } from '../components/Card'
import { CruxCard } from '../components/CruxCard'
import { GapsList } from '../components/GapsList'
import { HazardCard, NotEvaluatedCard } from '../components/HazardCard'
import { OutcomeLine } from '../components/OutcomeLine'
import { ScreenHeader } from '../components/ScreenHeader'
import { Timeline } from '../components/Timeline'
import { retryForecast } from '../api/queries'
import { conditionsAt, gustAt, nothingFlaggedRange } from '../domain/assessment'
import { computeArrivals, formatArrival, formatClock } from '../domain/timing'
import { useAssessmentView, type AssessmentView } from '../hooks/useAssessmentView'
import { STREAM_DELAY_MS, useDelayed } from '../hooks/useDelayed'
import { useT } from '../i18n'
import { formatShortDate, formatWeekday } from '../lib/format'
import { legsRange, routeName, stopById, stopLabel, stopWaypoint } from '../lib/route'
import { usePlan } from '../store/plan'

export function AssessmentScreen() {
  const view = useAssessmentView()
  // Remount on scenario change so streaming and retry state start fresh.
  return view.data.outcome === 'not_assessable' ? (
    <NotAssessable key={view.scenario} view={view} />
  ) : (
    <Assessed key={view.scenario} view={view} />
  )
}

function useHeaderSubtitle(view: AssessmentView) {
  const { t, lang } = useT()
  const date = usePlan((s) => s.date)
  return t('assess.headerMeta', {
    date: formatShortDate(date, lang),
    start: formatClock(view.start),
    grade: view.route.grade,
  })
}

function Assessed({ view }: { view: AssessmentView }) {
  const { t, lang } = useT()
  const navigate = useNavigate()
  const subtitle = useHeaderSubtitle(view)
  const date = usePlan((s) => s.date)
  const originalStart = usePlan((s) => s.originalStart)
  const setStart = usePlan((s) => s.setStart)
  const ready = useDelayed(STREAM_DELAY_MS)

  const { route, data, arrivals, evaluation, start, paceAnswer, search } = view
  const forecastTime = formatClock(data.forecast.issuedAt)
  const mapTo = { pathname: '/assessment/map', search }

  const crux = stopById(route, route.cruxStopId)
  const cruxWaypoint = stopWaypoint(route, crux.id)
  const cruxUnknown = evaluation.stopSeverity[crux.id] === 'unknown'
  const cruxConditions = cruxUnknown ? null : conditionsAt(data, crux.id, arrivals[crux.id])
  const showers = data.hazards.find((h) => h.kind === 'showers')

  const range = nothingFlaggedRange(route, evaluation.stopSeverity)
  const gaps = data.gaps.filter((gap) => !(gap === 'pace' && paceAnswer))

  const startAlt = data.alternatives.find(
    (a) =>
      a.kind === 'startEarlier' &&
      start > a.start &&
      evaluation.flagged.some((f) => f.hazard.id === a.dependsOn),
  )
  const routeAlts = data.alternatives.filter((a) => a.kind === 'altRoute')

  return (
    <>
      <ScreenHeader
        backTo="/"
        title={routeName(route)}
        subtitle={subtitle}
        action={<PillLink to={mapTo}>{t('assess.map')}</PillLink>}
      />

      <main className="flex flex-1 flex-col gap-3.5 px-[18px] pt-[18px] pb-2">
        <OutcomeLine data={data} notEvaluatedCount={evaluation.notEvaluatedLegs.length} />

        <CruxCard
          place={cruxWaypoint.name}
          elevationM={cruxWaypoint.elevationM}
          arrival={arrivals[crux.id]}
          gust={cruxUnknown ? null : gustAt(data, crux.id, arrivals[crux.id])}
          feelsLikeC={cruxConditions?.feelsLikeC ?? null}
          showersFrom={showers ? showers.window.from : null}
          stale={data.stale}
        />

        <Timeline
          route={route}
          arrivals={arrivals}
          stopSeverity={evaluation.stopSeverity}
          paceKnown={paceAnswer !== null}
          onSelect={() => navigate(mapTo)}
        />

        {ready ? (
          <>
            <section className="flex flex-col gap-2.5">
              <SectionTitle>{t('flagged.title')}</SectionTitle>
              {evaluation.flagged.map((flagged) => (
                <HazardCard key={flagged.hazard.id} flagged={flagged} />
              ))}
              {evaluation.notEvaluatedLegs.length > 0 && (
                <NotEvaluatedCard range={legsRange(route, evaluation.notEvaluatedLegs, t)} />
              )}
              {range && (
                <p className="px-1 pt-1.5 text-[13px] leading-normal text-muted">
                  {range === 'all'
                    ? t('flagged.nothingAll', { time: forecastTime })
                    : t('flagged.nothingOn', {
                        range: `${stopLabel(stopById(route, range.from), t)} → ${stopLabel(stopById(route, range.to), t)}`,
                        time: forecastTime,
                      })}
                </p>
              )}
            </section>

            <GapsList gaps={gaps} />

            <section className="flex flex-col gap-2.5">
              <SectionTitle>{t('alts.title')}</SectionTitle>
              {start !== originalStart && (
                <p role="status" className="px-1 text-[13px] text-plum">
                  {t('alts.applied', { start: formatClock(start) })}
                </p>
              )}
              {startAlt && startAlt.kind === 'startEarlier' && (
                <AlternativeCard
                  suggested
                  title={t('alt.startEarlier.title', { start: formatClock(startAlt.start) })}
                  body={t('alt.startEarlier.body', {
                    place: cruxWaypoint.name,
                    time: formatArrival(computeArrivals(route, startAlt.start, paceAnswer)[crux.id]),
                    boat: formatClock(route.lastBoat),
                  })}
                  badge={<span className="shrink-0 text-xs font-semibold text-plum">{t('alts.suggested')}</span>}
                  onSelect={() => setStart(startAlt.start)}
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
          </>
        ) : (
          <div aria-busy="true" className="flex flex-col gap-3.5">
            <Skeleton className="h-40" />
            <Skeleton className="h-28" />
            <Skeleton className="h-24" />
          </div>
        )}

        <Disclaimer>{t('disclaimer')}</Disclaimer>
      </main>

      <BottomAction>
        <Button className="flex-1" onClick={() => navigate('/preflight')}>
          {t('assess.cta')}
        </Button>
      </BottomAction>
    </>
  )
}

/** 02b: reason stated, official channels named, no hazards, no primary action. */
function NotAssessable({ view }: { view: AssessmentView }) {
  const { t, lang } = useT()
  const subtitle = useHeaderSubtitle(view)
  const date = usePlan((s) => s.date)
  const queryClient = useQueryClient()
  const [checking, setChecking] = useState(false)
  const [checkedAt, setCheckedAt] = useState(view.data.forecast.checkedAt)
  const beyondHorizon = view.data.forecast.unavailableReason === 'beyond_horizon'

  const retry = () => {
    setChecking(true)
    retryForecast(date)
      .then((result) => {
        setCheckedAt(result.checkedAt)
        // The source answers again: fetch the assessment rather than keep showing the outage.
        if (result.available) return queryClient.invalidateQueries({ queryKey: ['assessment', view.route.id] })
      })
      .catch(() => {})
      .finally(() => setChecking(false))
  }

  return (
    <>
      <ScreenHeader backTo="/" title={routeName(view.route)} subtitle={subtitle} />
      <main className="flex flex-1 flex-col gap-3.5 px-[18px] pt-[18px] pb-8">
        <OutcomeLine data={view.data} checkedAt={checkedAt} />
        <Card className="flex flex-col gap-3 px-[18px] py-5">
          <h2 className="font-serif text-2xl leading-[1.2] font-medium text-pretty">{t('na.title')}</h2>
          <p className="text-[15px] leading-normal">
            {beyondHorizon
              ? t('na.reasonBeyondHorizon', { date: formatShortDate(date, lang) })
              : t('na.reason', { time: formatClock(view.data.forecast.unavailableSince) })}
          </p>
          <p className="text-sm leading-[1.6] text-ink-3">
            {t('na.checkDirectly')}
            <br />
            <a className="font-semibold" href="https://www.meteoswiss.admin.ch/local-forecasts.html" target="_blank" rel="noreferrer">
              {t('na.meteoswiss')}
            </a>
            <br />
            <a className="font-semibold" href="https://www.slf.ch/en/avalanche-bulletin-and-snow-situation/" target="_blank" rel="noreferrer">
              {t('na.slf')}
            </a>
            <br />
            {view.route.toName} · <a href="tel:+41336761437">+41 33 676 14 37</a>
          </p>
          <Button variant="accent" size="md" className="mt-1" onClick={retry} disabled={checking}>
            {checking ? t('na.retrying') : t('na.retry')}
          </Button>
        </Card>
        <p className="px-1 text-[13px] leading-normal text-muted">{t('na.footnote')}</p>
      </main>
    </>
  )
}
