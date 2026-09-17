import { useT } from '../i18n'
import { SparkleIcon } from './icons'

/** "Nemotron" for the model this app is deployed with, "AI" for any other. */
function modelName(model: string | undefined, fallback: string): string {
  return model && /nemotron/i.test(model) ? 'Nemotron' : fallback
}

interface Props {
  model?: string
  /** `pending` pulses while the model is still working. */
  state?: 'done' | 'pending'
  /** On the dark field surface. */
  dark?: boolean
  className?: string
}

/**
 * The mark on anything a language model wrote: a sparkle and the model's name, in the AI hue, which is
 * neither a severity colour nor the action plum. The full "worded by a language model" note is its
 * tooltip and accessible name, so the card itself stays short.
 */
export function AiBadge({ model, state = 'done', dark = false, className = '' }: Props) {
  const { t } = useT()
  const name = modelName(model, t('ai.generic'))
  const label = state === 'pending' ? t('ai.phrasing', { model: name }) : t('ai.worded', { model: name })
  const colours = dark ? 'bg-ai-dark-soft text-ai-dark' : 'bg-ai-soft text-ai'
  return (
    <span
      title={label}
      aria-label={label}
      role="note"
      className={`inline-flex h-5 shrink-0 items-center gap-1 rounded-full px-2 text-[11px] font-semibold ${colours} ${className}`}
    >
      <SparkleIcon className={`size-3 ${state === 'pending' ? 'ai-pulse' : ''}`} />
      <span aria-hidden="true">{state === 'pending' ? t('ai.phrasingShort', { model: name }) : name}</span>
    </span>
  )
}
