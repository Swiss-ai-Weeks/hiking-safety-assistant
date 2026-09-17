import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { retryForecast } from '../../api/queries'
import { formatClock } from '../../domain/timing'
import type { AssessmentView } from '../../hooks/useAssessmentView'
import { useT } from '../../i18n'
import { formatShortDate } from '../../lib/format'
import { usePlan } from '../../store/plan'
import { Button } from '../Button'
import { OutcomeLine } from '../OutcomeLine'

/** No forecast: reason stated, official channels named, no hazards and no plan built on nothing. */
export function NotAssessablePanel({ view }: { view: AssessmentView }) {
  const { t, lang } = useT()
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
    <div className="flex flex-col gap-3">
      <OutcomeLine data={view.data} checkedAt={checkedAt} />
      <div className="flex flex-col gap-3 rounded-card border border-line bg-card px-[18px] py-5">
        <h3 className="font-serif text-2xl leading-[1.2] font-medium text-pretty">{t('na.title')}</h3>
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
        </p>
        <Button variant="accent" size="md" className="mt-1" onClick={retry} disabled={checking}>
          {checking ? t('na.retrying') : t('na.retry')}
        </Button>
      </div>
      <p className="text-[13px] leading-normal text-muted">{t('na.footnote')}</p>
    </div>
  )
}
