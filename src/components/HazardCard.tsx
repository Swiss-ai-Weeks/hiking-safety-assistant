import type { FlaggedHazard } from '../domain/assessment'
import { formatClock } from '../domain/timing'
import { useT } from '../i18n'
import { SeverityDot } from './Severity'

/** Severity dot, place + time title, template body, optional "Lifts if", provenance footnote. */
export function HazardCard({ flagged }: { flagged: FlaggedHazard }) {
  const { t } = useT()
  const { hazard, severity } = flagged
  const params = {
    place: hazard.place ?? '',
    from: formatClock(hazard.window.from),
    to: formatClock(hazard.window.to),
  }

  return (
    <article className="flex gap-3 rounded-card border border-line bg-card p-4">
      <SeverityDot severity={severity} className="mt-1.5" />
      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="text-base leading-[1.3] font-semibold">{t(`hazard.${hazard.kind}.title` as const, params)}</h3>
        <p className="text-sm leading-normal text-ink-2">{t(`hazard.${hazard.kind}.body` as const, params)}</p>
        {hazard.hasLiftsIf && (
          <p className="text-[13px] leading-normal text-muted">
            <strong className="font-semibold text-ink-3">{t('flagged.liftsIf')}</strong>{' '}
            {t(`hazard.${hazard.kind}.liftsIf` as const, params)}
          </p>
        )}
        <p className="text-xs text-faint">{hazard.provenance}</p>
      </div>
    </article>
  )
}

export function NotEvaluatedCard({ range }: { range: string }) {
  const { t } = useT()
  return (
    <article className="flex gap-3 rounded-card border-[1.5px] border-dashed border-line p-4">
      <SeverityDot severity="unknown" className="mt-1.5" />
      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="text-base leading-[1.3] font-semibold">{t('flagged.notEvaluated', { range })}</h3>
        <p className="text-sm leading-normal text-ink-2">{t('flagged.notEvaluatedBody')}</p>
      </div>
    </article>
  )
}
