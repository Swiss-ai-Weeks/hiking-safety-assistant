import type { AssessmentData, Minutes } from '../domain/types'
import { formatClock } from '../domain/timing'
import { useT } from '../i18n'

interface Props {
  data: AssessmentData
  /** Overrides the forecast's last check (after "Try again"). */
  checkedAt?: Minutes
  notEvaluatedCount?: number
}

/** Single source of truth for the assessment state, at the top of 02. */
export function OutcomeLine({ data, checkedAt, notEvaluatedCount = 0 }: Props) {
  const { t } = useT()
  const time = formatClock(data.forecast.issuedAt)

  let dot = 'bg-ink'
  let label = t('outcome.assessed')
  let detail = t('outcome.assessedDetail', { time })

  if (data.outcome === 'not_assessable') {
    dot = 'bg-sev-high'
    label = t('outcome.notAssessable')
    detail = t('outcome.notAssessableDetail', { time: formatClock(checkedAt ?? data.forecast.checkedAt) })
  } else if (data.outcome === 'partial') {
    dot = 'bg-sev-mod'
    label = t('outcome.partial')
    detail = t('outcome.partialDetail', { count: notEvaluatedCount, time })
  } else if (data.stale) {
    dot = 'bg-sev-mod'
    detail = t('outcome.staleDetail', { time, hours: data.forecast.staleHours })
  }

  return (
    <div role="status" className="flex flex-wrap items-center gap-x-2 text-[13px] text-ink-3">
      <span aria-hidden="true" className={`size-2 rounded-full ${dot}`} />
      <span className="font-semibold">{label}</span>
      <span className="text-faint">{detail}</span>
    </div>
  )
}
