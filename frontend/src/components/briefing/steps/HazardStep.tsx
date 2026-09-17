import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { narrationQuery } from '../../../api/queries'
import type { FlaggedHazard } from '../../../domain/assessment'
import { formatClock } from '../../../domain/timing'
import type { HazardKind } from '../../../domain/types'
import { useT } from '../../../i18n'
import { hazardText } from '../../../i18n/hazardCopy'
import { legsRange } from '../../../lib/route'
import { usePlan } from '../../../store/plan'
import { AiBadge } from '../../AiBadge'
import { ChevronRight } from '../../icons'
import { GapsList } from '../../GapsList'
import { HazardCard, NotEvaluatedCard } from '../../HazardCard'
import { OutcomeLine } from '../../OutcomeLine'
import { SeverityDot } from '../../Severity'
import { HAZARD_ORDER } from '../model'
import { resolvedChecks } from '../stepMaps'
import type { StepProps } from './types'

function Pending() {
  return (
    <span
      aria-hidden="true"
      className="inline-block size-2.5 shrink-0 animate-spin rounded-full border-[1.5px] border-line border-t-plum"
    />
  )
}

export function HazardPanel({ view, progress }: StepProps) {
  const { t, lang } = useT()
  const date = usePlan((s) => s.date)
  const [open, setOpen] = useState<HazardKind | null>(null)
  const { route, data, evaluation, paceAnswer, scenario } = view
  // Not blocking: until (or unless) it answers, the cards keep their templates.
  const narrationResult = useQuery(narrationQuery(route.id, scenario, date, lang))
  const narration = narrationResult.data
  const resolved = resolvedChecks(progress)
  const done = resolved >= HAZARD_ORDER.length
  const gaps = data.gaps.filter((gap) => !(gap === 'pace' && paceAnswer))
  const forecastTime = formatClock(data.forecast.issuedAt)

  const byKind = new Map<HazardKind, FlaggedHazard>()
  for (const flagged of evaluation.flagged) if (!byKind.has(flagged.hazard.kind)) byKind.set(flagged.hazard.kind, flagged)

  return (
    <div className="flex flex-col gap-3">
      <OutcomeLine data={data} notEvaluatedCount={evaluation.notEvaluatedLegs.length} />

      <ul className="flex flex-col" aria-busy={!done}>
        {HAZARD_ORDER.map((kind, i) => {
          const isResolved = i < resolved
          const flagged = isResolved ? byKind.get(kind) : undefined
          const expanded = open === kind && flagged
          const row = (
            <>
              {isResolved ? <SeverityDot severity={flagged?.severity ?? 'none'} /> : <Pending />}
              <span className={`min-w-0 flex-1 ${flagged ? 'font-semibold' : ''}`}>{t(`brief.check.${kind}` as const)}</span>
              <span
                className={`min-w-0 truncate text-right text-[13px] ${flagged ? (flagged.severity === 'high' ? 'text-sev-high' : 'text-ink-2') : 'text-muted'}`}
              >
                {!isResolved ? '' : flagged ? hazardText(lang, flagged.hazard, 'short') : t('legend.none')}
              </span>
            </>
          )
          return (
            <li key={kind} className="border-b border-divider last:border-0">
              {flagged ? (
                <button
                  type="button"
                  aria-expanded={Boolean(expanded)}
                  onClick={() => setOpen(expanded ? null : kind)}
                  className="check-resolve flex min-h-11 w-full items-center gap-3 py-2 text-left text-[15px]"
                >
                  {row}
                  <ChevronRight className={`shrink-0 text-chevron transition-transform ${expanded ? 'rotate-90' : ''}`} />
                </button>
              ) : (
                <div className={`flex min-h-11 items-center gap-3 py-2 text-[15px] ${isResolved ? 'check-resolve' : 'text-muted'}`}>
                  {row}
                </div>
              )}
              {expanded && (
                <div className="flex flex-col gap-1.5 pb-3">
                  {narrationResult.isPending && <AiBadge state="pending" model="nemotron" className="self-end" />}
                  <HazardCard
                    flagged={flagged}
                    narrated={narration?.hazards.find((h) => h.id === flagged.hazard.id)}
                    model={narration?.model}
                  />
                </div>
              )}
            </li>
          )
        })}
      </ul>

      {done && (
        <>
          {evaluation.notEvaluatedLegs.length > 0 && (
            <NotEvaluatedCard range={legsRange(route, evaluation.notEvaluatedLegs, t)} />
          )}
          <GapsList gaps={gaps} />
          <p role="status" className="text-[13px] text-muted">
            {evaluation.flagged.length > 0
              ? t('brief.checkSummary', { count: evaluation.flagged.length, time: forecastTime })
              : evaluation.notEvaluatedLegs.length > 0
                ? t('brief.nothingChecked', { time: forecastTime })
                : t('flagged.nothingAll', { time: forecastTime })}
          </p>
        </>
      )}
    </div>
  )
}
