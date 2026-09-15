import { useState, type ReactNode } from 'react'
import shareCardPhoto from '../assets/share-card.jpg'
import { BottomAction } from '../components/BottomAction'
import { Button } from '../components/Button'
import { ScreenHeader } from '../components/ScreenHeader'
import { formatClock } from '../domain/timing'
import { useAssessmentView } from '../hooks/useAssessmentView'
import { useT } from '../i18n'
import { formatDateTime, formatKm, formatShortDate, formatWeekday } from '../lib/format'
import { routeName, stopWaypoint } from '../lib/route'
import { usePlan, useTurnaround } from '../store/plan'

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">{label}</h3>
      {children}
    </div>
  )
}

/** 05: one screen the whole group can point at. "The plan says we turn here." */
export function ShareScreen() {
  const { t, lang } = useT()
  const { route, data, evaluation, start } = useAssessmentView()
  const date = usePlan((s) => s.date)
  const turnaround = useTurnaround()
  const groupSize = usePlan((s) => s.groupSize)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const hikeStartedAt = usePlan((s) => s.hikeStartedAt)
  const savePlan = usePlan((s) => s.savePlan)
  const [openedAt] = useState(() => Date.now())
  const [feedback, setFeedback] = useState<'copied' | 'saved' | null>(null)

  const crux = stopWaypoint(route, route.cruxStopId)
  const name = routeName(route)
  const rule = t('share.turnRule', { place: crux.name, time: formatClock(turnaround), bailout: route.bailoutName })
  const watchFor =
    data.outcome === 'not_assessable'
      ? t('na.title')
      : evaluation.flagged.length > 0
        ? evaluation.flagged
            .map(({ hazard }) => t(`hazard.${hazard.kind}.watch` as const, { from: formatClock(hazard.window.from) }))
            .join(' ')
        : t('share.watchNothing', { time: formatClock(data.forecast.issuedAt) })

  const onShare = async () => {
    const text = t('share.text', { route: name, date: formatShortDate(date, lang), rule })
    const url = window.location.href
    try {
      if (navigator.share) {
        await navigator.share({ title: name, text, url })
        return
      }
      await navigator.clipboard.writeText(`${text}\n${url}`)
      setFeedback('copied')
    } catch {
      // Share sheet dismissed or clipboard blocked.
    }
  }

  return (
    <>
      <ScreenHeader
        bordered={false}
        backTo={hikeStarted ? '/field' : '/preflight'}
        title={t('share.title', { day: formatWeekday(date, lang) })}
      />

      <main className="flex-1 px-[22px] pt-2 pb-2">
        <article className="overflow-hidden rounded-sheet border border-line bg-card">
          <div className="relative h-[300px] text-white">
            <img src={shareCardPhoto} alt={t('share.photoAlt')} className="absolute inset-0 size-full object-cover" />
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-[linear-gradient(rgba(20,18,16,0)_40%,rgba(20,18,16,0.88)_62%,rgba(20,18,16,0.92)_100%)]"
            />
            <div className="absolute inset-x-5 bottom-[18px]">
              <p className="text-xs font-semibold tracking-[0.08em] text-crux-body uppercase">
                {t('share.eyebrow', { date: formatShortDate(date, lang), count: groupSize })}
              </p>
              <h2 className="mt-1.5 font-serif text-2xl leading-[1.2] font-medium">{name}</h2>
              <p className="mt-1 text-sm text-[oklch(0.9_0.01_75)]">
                {t('share.meta', {
                  grade: route.grade,
                  km: formatKm(route.distanceKm, lang),
                  start: formatClock(start),
                  boat: formatClock(route.lastBoat),
                })}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-4 px-5 py-[18px]">
            <Block label={t('share.turnIf')}>
              <p className="text-[17px] leading-[1.4] font-semibold">{rule}</p>
            </Block>
            <Block label={t('share.watchFor')}>
              <p className="text-[15px] leading-normal text-ink-2">{watchFor}</p>
            </Block>
            <Block label={t('share.notChecked')}>
              <p className="text-[15px] leading-normal text-ink-2">{t('share.notCheckedBody')}</p>
            </Block>
            <p className="border-t border-divider pt-3 text-xs leading-normal text-faint">
              {t('share.provenance', {
                made: formatDateTime(hikeStartedAt ?? openedAt, lang),
                model: data.forecast.model,
                issued: formatClock(data.forecast.issuedAt),
              })}
            </p>
          </div>
        </article>
        {feedback && (
          <p role="status" className="px-1 pt-3 text-center text-[13px] text-muted">
            {t(feedback === 'copied' ? 'share.copied' : 'share.saved')}
          </p>
        )}
      </main>

      <BottomAction>
        <Button className="flex-1" onClick={onShare}>
          {t('share.share')}
        </Button>
        <Button
          variant="secondary"
          className="w-[120px]"
          onClick={() => {
            savePlan(route)
            setFeedback('saved')
          }}
        >
          {t('share.save')}
        </Button>
      </BottomAction>
    </>
  )
}
