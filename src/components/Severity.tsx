import type { StopSeverity } from '../domain/types'
import { useT } from '../i18n'
import { SEVERITY_BG } from '../lib/ui'

export function SeverityDot({ severity, className = '' }: { severity: StopSeverity; className?: string }) {
  const { t } = useT()
  return (
    <>
      <span aria-hidden="true" className={`inline-block size-2.5 shrink-0 rounded-full ${SEVERITY_BG[severity]} ${className}`} />
      {severity !== 'unknown' && <span className="sr-only">{t(`legend.${severity}` as const)}</span>}
    </>
  )
}

export function SeverityLegend({ className = '' }: { className?: string }) {
  const { t } = useT()
  return (
    <div
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[10px] border border-line bg-white/92 px-2.5 py-1.5 text-[11px] text-ink-3 ${className}`}
    >
      {(['none', 'mod', 'high'] as const).map((s) => (
        <span key={s} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={`h-1 w-3.5 rounded-sm ${SEVERITY_BG[s]}`} />
          {t(`legend.${s}` as const)}
        </span>
      ))}
    </div>
  )
}
