import { useState, type FormEvent } from 'react'
import { useT } from '../../i18n'
import { SendIcon, SparkleIcon } from '../icons'

interface Props {
  onSend: (question: string) => void
  pending: boolean
  placeholder: string
  dark?: boolean
  onFocus?: () => void
}

/** The always-visible field for talking to the model. */
export function AskComposer({ onSend, pending, placeholder, dark = false, onFocus }: Props) {
  const { t } = useT()
  const [value, setValue] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!value.trim() || pending) return
    onSend(value)
    setValue('')
  }

  const surface = dark
    ? 'border-white/10 bg-field-control text-white placeholder:text-field-hint focus-within:border-ai-dark'
    : 'border-line bg-card text-ink placeholder:text-faint focus-within:border-ai'

  return (
    <form onSubmit={submit} className={`flex h-12 items-center gap-2 rounded-full border-[1.5px] pr-1.5 pl-3.5 ${surface}`}>
      <SparkleIcon className={`size-4 shrink-0 ${dark ? 'text-ai-dark' : 'text-ai'}`} />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onFocus={onFocus}
        maxLength={300}
        enterKeyHint="send"
        aria-label={placeholder}
        placeholder={placeholder}
        className="min-w-0 flex-1 bg-transparent text-[16px] outline-none placeholder:text-inherit placeholder:opacity-70"
      />
      <button
        type="submit"
        aria-label={t('ask.send')}
        disabled={!value.trim() || pending}
        className={`flex size-9 shrink-0 items-center justify-center rounded-full text-white transition-opacity disabled:opacity-35 ${
          dark ? 'bg-ai-dark text-field' : 'bg-ai'
        }`}
      >
        <SendIcon className="size-[18px]" />
      </button>
    </form>
  )
}
