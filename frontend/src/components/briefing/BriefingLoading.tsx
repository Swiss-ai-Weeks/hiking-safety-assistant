import { useT } from '../../i18n'
import { Skeleton } from '../Card'

/**
 * The briefing's shape while its code and the assessment load: header, map, then the sheet saying
 * what is being worked out. The assessment reads live weather, so this can be on screen a while.
 */
export function BriefingLoading() {
  const { t } = useT()
  return (
    <div role="status" aria-live="polite" className="flex h-dvh flex-col">
      <div className="flex items-center gap-2 border-b border-rule px-3.5 pt-[max(env(safe-area-inset-top),12px)] pb-2.5">
        <span className="size-10 shrink-0" />
        <div className="flex flex-1 flex-col gap-1.5">
          <Skeleton className="h-3.5 w-2/5 rounded-full" />
          <Skeleton className="h-3 w-3/5 rounded-full" />
        </div>
      </div>

      <div aria-hidden="true" className="h-[40dvh] min-h-[220px] shrink-0 animate-pulse bg-subtle" />

      <section className="relative z-10 -mt-4 flex flex-1 flex-col items-center gap-3 rounded-t-sheet border-t border-line bg-canvas px-[18px] pt-10 text-center shadow-[0_-6px_20px_rgba(0,0,0,0.08)]">
        <span
          aria-hidden="true"
          className="size-8 rounded-full border-[3px] border-line border-t-plum motion-safe:animate-spin"
        />
        <p className="text-[15px] font-semibold">{t('brief.loading')}</p>
        <p className="max-w-[280px] text-[13px] leading-normal text-muted">{t('brief.loadingDetail')}</p>
      </section>
    </div>
  )
}
