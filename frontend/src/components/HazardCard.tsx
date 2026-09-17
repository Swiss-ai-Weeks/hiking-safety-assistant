import type { FlaggedHazard } from '../domain/assessment'
import type { NarratedHazard } from '../domain/types'
import { useT } from '../i18n'
import { hazardText, narratedBody } from '../i18n/hazardCopy'
import { SeverityDot } from './Severity'

/**
 * Severity dot, place + time title, body, optional "Lifts if", provenance footnote.
 *
 * The body is the template until `narrated` arrives with one that passes the copy rules; then it is
 * that, labelled as worded by a model. Its citations are linked whether or not there is a body.
 */
export function HazardCard({ flagged, narrated }: { flagged: FlaggedHazard; narrated?: NarratedHazard }) {
  const { t, lang } = useT()
  const { hazard, severity } = flagged
  const liftsIf = hazard.hasLiftsIf ? hazardText(lang, hazard, 'liftsIf') : null
  const phrased = narratedBody(lang, hazard, narrated?.body)
  const citations = narrated?.citations ?? []

  return (
    <article className="flex gap-3 rounded-card border border-line bg-card p-4">
      <SeverityDot severity={severity} className="mt-1.5" />
      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="text-base leading-[1.3] font-semibold">{hazardText(lang, hazard, 'title')}</h3>
        <p className="text-sm leading-normal text-ink-2">{phrased ?? hazardText(lang, hazard, 'body')}</p>
        {liftsIf && (
          <p className="text-[13px] leading-normal text-muted">
            <strong className="font-semibold text-ink-3">{t('flagged.liftsIf')}</strong>{' '}
            {liftsIf}
          </p>
        )}
        <p className="text-xs text-faint">{hazard.provenance}</p>
        {phrased && <p className="text-xs text-faint">{t('flagged.narrated')}</p>}
        {citations.length > 0 && (
          <p className="text-xs text-faint">
            {t('flagged.guidance')}{' '}
            {citations.map((citation, i) => (
              <span key={citation.id}>
                {i > 0 && ' · '}
                <a className="underline" href={citation.url} target="_blank" rel="noreferrer">
                  {citation.title}
                </a>
              </span>
            ))}
          </p>
        )}
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
