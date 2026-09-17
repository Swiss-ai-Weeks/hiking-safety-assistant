import { useT } from '../../i18n'
import { SparkleIcon } from '../icons'

export const STEP_COUNT = 5

interface Props {
  step: number
  title: string
  /** Steps past this one can't be jumped to (no forecast, no checks). */
  lastStep: number
  onSelect: (step: number) => void
  /** Shown once the step's animation has played. */
  onReplay?: () => void
  /** Opens the conversation. Here rather than a composer held open below the step. */
  onAsk: () => void
}

/** Progress dots (each a way to that step), the step's name, and a way to watch it again. */
export function StepHeader({ step, title, lastStep, onSelect, onReplay, onAsk }: Props) {
  const { t } = useT()
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        <nav className="-ml-1.5 flex items-center" aria-label={t('brief.stepOf', { n: step, total: STEP_COUNT })}>
          {Array.from({ length: STEP_COUNT }, (_, i) => (
            <button
              key={i}
              type="button"
              disabled={i + 1 > lastStep}
              aria-current={i + 1 === step ? 'step' : undefined}
              aria-label={t('brief.stepOf', { n: i + 1, total: STEP_COUNT })}
              onClick={() => onSelect(i + 1)}
              className="flex h-6 items-center px-1.5 disabled:opacity-40"
            >
              <span
                className={`block h-1.5 rounded-full transition-all duration-300 ${
                  i + 1 === step ? 'w-5 bg-plum' : i + 1 < step ? 'w-1.5 bg-plum/60' : 'w-1.5 bg-line'
                }`}
              />
            </button>
          ))}
        </nav>
        <h2 className="font-serif text-[22px] leading-[1.2] font-medium">{title}</h2>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {onReplay && (
          <button
            type="button"
            onClick={onReplay}
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold text-plum hover:bg-subtle"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 12a9 9 0 1 0 3-6.7" />
              <path d="M3 4v5h5" />
            </svg>
            {t('brief.replay')}
          </button>
        )}
        <button
          type="button"
          onClick={onAsk}
          className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border-[1.5px] border-line px-3 text-[13px] font-semibold text-ink-2 hover:border-ai"
        >
          <SparkleIcon className="size-4 text-ai" />
          {t('ask.short')}
        </button>
      </div>
    </div>
  )
}
