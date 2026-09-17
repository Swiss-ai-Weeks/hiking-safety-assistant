import { useEffect, useRef, type ReactNode } from 'react'
import type { ChatMessage } from '../../domain/types'
import { useT } from '../../i18n'
import { verdictsIn } from '../../i18n/copyRules'
import { AiBadge } from '../AiBadge'
import { SparkleIcon } from '../icons'
import type { AskState } from './useAsk'

/** A message from the app itself (the plan, a check-in): the rules speaking, so no model badge. */
export interface AppMessage {
  id: string
  at: number
  eyebrow: string
  body: ReactNode
  tone?: 'plain' | 'alert'
}

interface Props {
  ask: AskState
  suggestions: string[]
  appMessages?: AppMessage[]
  dark?: boolean
}

function Answer({ message, dark }: { message: ChatMessage; dark: boolean }) {
  const { t, lang } = useT()
  // The server already refused verdict wording; checked again before it is shown, as narration is.
  const text = message.reason === 'ok' && message.text && verdictsIn(message.text, lang).length === 0 ? message.text : null
  const muted = dark ? 'text-field-muted' : 'text-muted'
  return (
    <div className={`flex max-w-[92%] flex-col gap-1.5 self-start rounded-2xl rounded-tl-md px-3.5 py-2.5 ${dark ? 'bg-field-card' : 'border border-ai-line bg-card'}`}>
      <AiBadge model={message.model} dark={dark} className="self-start" />
      {text ? (
        <p className="text-[15px] leading-normal whitespace-pre-line">{text}</p>
      ) : (
        <p className={`text-[15px] leading-normal ${muted}`}>{t(`ask.reason.${message.reason === 'ok' || !message.reason ? 'dropped' : message.reason}` as const)}</p>
      )}
      {text && message.citations && message.citations.length > 0 && (
        <p className={`text-xs ${muted}`}>
          {t('ask.sources')}{' '}
          {message.citations.map((citation, i) => (
            <span key={citation.id}>
              {i > 0 && ' · '}
              <a className={`underline ${dark ? 'text-ai-dark' : ''}`} href={citation.url} target="_blank" rel="noreferrer">
                {citation.publisher}
              </a>
            </span>
          ))}
        </p>
      )}
    </div>
  )
}

/** The thread: the app's own messages and the conversation with the model, oldest first. */
export function AskConversation({ ask, suggestions, appMessages = [], dark = false }: Props) {
  const { t } = useT()
  const end = useRef<HTMLDivElement>(null)
  const { messages, pending, failure, send, clear } = ask

  const items = [
    ...appMessages.map((m) => ({ kind: 'app' as const, at: m.at, id: m.id, app: m })),
    ...messages.map((m) => ({ kind: 'chat' as const, at: m.at, id: m.id, chat: m })),
  ].sort((a, b) => a.at - b.at)

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end', behavior: 'smooth' })
  }, [items.length, pending])

  const muted = dark ? 'text-field-muted' : 'text-muted'
  const asked = messages.some((m) => m.role === 'user')

  return (
    <div className="flex flex-col gap-2.5" aria-live="polite">
      {items.map((item) =>
        item.kind === 'app' ? (
          <div
            key={item.id}
            className={`flex flex-col gap-0.5 rounded-2xl px-3.5 py-2.5 ${
              item.app.tone === 'alert'
                ? 'border-2 border-sev-high'
                : dark
                  ? 'bg-field-card/60'
                  : 'bg-subtle'
            }`}
          >
            <span className={`text-[11px] font-semibold tracking-[0.06em] uppercase ${item.app.tone === 'alert' ? 'text-sev-high' : muted}`}>
              {item.app.eyebrow}
            </span>
            <div className="text-[15px] leading-snug font-medium">{item.app.body}</div>
          </div>
        ) : item.chat.role === 'user' ? (
          <p
            key={item.id}
            className={`max-w-[85%] self-end rounded-2xl rounded-tr-md px-3.5 py-2 text-[15px] leading-snug ${
              dark ? 'bg-ai-dark-soft text-white' : 'bg-ai text-white'
            }`}
          >
            {item.chat.text}
          </p>
        ) : (
          <Answer key={item.id} message={item.chat} dark={dark} />
        ),
      )}

      {pending && (
        <p className={`flex items-center gap-2 self-start text-sm ${dark ? 'text-ai-dark' : 'text-ai'}`} role="status">
          <SparkleIcon className="ai-pulse size-4" />
          {t('ask.thinking')}
        </p>
      )}
      {failure && (
        <p role="alert" className={`self-start text-sm ${muted}`}>
          {t(failure === 'tooMany' ? 'ask.tooMany' : 'ask.failed')}
        </p>
      )}

      {!asked && !pending && (
        <div className="flex flex-col gap-2 pt-1">
          <p className={`text-[13px] leading-snug ${muted}`}>{t('ask.intro')}</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => void send(suggestion)}
                className={`rounded-full border-[1.5px] px-3 py-1.5 text-left text-[13px] font-medium ${
                  dark ? 'border-white/15 text-white hover:border-ai-dark' : 'border-ai-line text-ai hover:border-ai'
                }`}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}
      {asked && !pending && (
        <button type="button" onClick={clear} className={`self-center text-xs underline ${muted}`}>
          {t('ask.clear')}
        </button>
      )}
      <div ref={end} />
    </div>
  )
}
