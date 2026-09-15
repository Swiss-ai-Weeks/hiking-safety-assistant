import { useSuspenseQuery } from '@tanstack/react-query'
import { useState, type MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { recentRoutesQuery } from '../api/queries'
import { BottomAction } from '../components/BottomAction'
import { Button } from '../components/Button'
import { Card, Eyebrow } from '../components/Card'
import { ChevronRight, SettingsIcon } from '../components/icons'
import { formatClock, parseClock } from '../domain/timing'
import { useT } from '../i18n'
import { formatDayMonth, formatInt, formatKm, formatShortDate } from '../lib/format'
import { routeName } from '../lib/route'
import { usePlan, useRoute } from '../store/plan'

function openPicker(event: MouseEvent<HTMLInputElement>) {
  try {
    event.currentTarget.showPicker()
  } catch {
    // Not supported or not allowed; the native control still works.
  }
}

export function PlanScreen() {
  const { t, lang } = useT()
  const navigate = useNavigate()
  const route = useRoute()
  const { data: recentRoutes } = useSuspenseQuery(recentRoutesQuery)
  const date = usePlan((s) => s.date)
  const start = usePlan((s) => s.start)
  const saved = usePlan((s) => s.saved)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const setDate = usePlan((s) => s.setDate)
  const setPlannedStart = usePlan((s) => s.setPlannedStart)
  const checkConditions = usePlan((s) => s.checkConditions)
  const reopenPlan = usePlan((s) => s.reopenPlan)
  const [demoNote, setDemoNote] = useState(false)

  return (
    <>
      <div className="flex items-start justify-between gap-3 px-[22px] pt-[max(env(safe-area-inset-top),40px)]">
        <div>
          <Eyebrow className="text-[13px]">{t('plan.eyebrow')}</Eyebrow>
          <h1 className="mt-1.5 font-serif text-[30px] leading-[1.15] font-medium text-pretty">{t('plan.title')}</h1>
        </div>
        <Link
          to="/settings"
          aria-label={t('common.settings')}
          className="-mr-2 flex size-11 shrink-0 items-center justify-center rounded-full text-plum hover:bg-subtle"
        >
          <SettingsIcon />
        </Link>
      </div>

      <main className="flex flex-1 flex-col gap-3.5 px-[22px] pt-6 pb-2">
        {hikeStarted && (
          <Link
            to="/field"
            className="flex items-center justify-between rounded-card bg-ink px-4 py-3.5 text-[15px] font-semibold text-white hover:text-white"
          >
            {t('pre.toField')}
            <ChevronRight />
          </Link>
        )}

        <Card className="overflow-hidden">
          <button
            type="button"
            onClick={() => setDemoNote((v) => !v)}
            aria-expanded={demoNote}
            className="flex w-full items-center justify-between gap-3 border-b border-divider px-4 py-3.5 text-left"
          >
            <span className="flex min-w-0 flex-col gap-[3px]">
              <span className="text-xs text-muted">{t('plan.route')}</span>
              <span className="text-[17px] font-medium">{routeName(route)}</span>
              <span className="text-[13px] text-muted">
                {t('plan.routeMeta', {
                  grade: route.grade,
                  km: formatKm(route.distanceKm, lang),
                  ascent: formatInt(route.ascentM),
                })}
              </span>
            </span>
            <ChevronRight className="shrink-0 text-chevron" />
          </button>
          <div className="flex">
            <label className="relative flex flex-1 flex-col gap-[3px] border-r border-divider px-4 py-3.5 focus-within:bg-subtle">
              <span className="text-xs text-muted">{t('plan.date')}</span>
              <span className="text-[17px] font-medium">{formatShortDate(date, lang)}</span>
              <input
                type="date"
                value={date}
                disabled={hikeStarted}
                onClick={openPicker}
                onChange={(e) => e.target.value && setDate(e.target.value)}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
            </label>
            <label className="relative flex flex-1 flex-col gap-[3px] px-4 py-3.5 focus-within:bg-subtle">
              <span className="text-xs text-muted">{t('plan.start')}</span>
              <span className="text-[17px] font-medium tabular-nums">{formatClock(start)}</span>
              <input
                type="time"
                step={300}
                value={formatClock(start)}
                disabled={hikeStarted}
                onClick={openPicker}
                onChange={(e) => {
                  const minutes = parseClock(e.target.value)
                  if (minutes !== null) setPlannedStart(minutes)
                }}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
            </label>
          </div>
        </Card>

        {demoNote && (
          <p role="status" className="px-1 text-[13px] text-plum">
            {t('plan.demoOnly')}
          </p>
        )}

        <p className="px-1 text-[13px] leading-normal text-muted">{t('plan.sourceNote')}</p>

        <section className="mt-2 flex flex-col gap-2">
          <Eyebrow className="px-1 pb-0.5 tracking-[0.06em]">{t('plan.recent')}</Eyebrow>
          {saved.map((plan) => (
            <button
              key={plan.id}
              type="button"
              onClick={() => {
                reopenPlan(plan)
                navigate('/assessment')
              }}
              className="flex items-center justify-between gap-3 rounded-control border border-line bg-card px-4 py-3 text-left hover:bg-subtle"
            >
              <span>
                <span className="block text-[15px] font-medium">{plan.routeName}</span>
                <span className="block text-[13px] text-muted">
                  {t('plan.savedMeta', { grade: plan.grade, date: formatShortDate(plan.date, lang), start: formatClock(plan.start) })}
                </span>
              </span>
              <ChevronRight className="shrink-0 text-chevron" />
            </button>
          ))}
          {recentRoutes.map((recent) => (
            <button
              key={recent.id}
              type="button"
              onClick={() => setDemoNote(true)}
              className="flex items-center justify-between gap-3 rounded-control border border-line bg-card px-4 py-3 text-left hover:bg-subtle"
            >
              <span>
                <span className="block text-[15px] font-medium">{recent.name}</span>
                <span className="block text-[13px] text-muted">
                  {t('plan.recentMeta', { grade: recent.grade, date: formatDayMonth(recent.checkedOn, lang) })}
                </span>
              </span>
              <ChevronRight className="shrink-0 text-chevron" />
            </button>
          ))}
        </section>
      </main>

      <BottomAction>
        <Button
          className="flex-1"
          onClick={() => {
            checkConditions()
            navigate('/assessment')
          }}
        >
          {t('plan.cta')}
        </Button>
      </BottomAction>
    </>
  )
}
