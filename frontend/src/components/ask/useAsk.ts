import { useState } from 'react'
import { askRoute } from '../../api/queries'
import { ApiError } from '../../api/client'
import type { AskTurn, ChatMessage, LiveContext, PlanContext, Route, Scenario } from '../../domain/types'
import { useT } from '../../i18n'
import { conversationKey, usePlan } from '../../store/plan'

const HISTORY_TURNS = 4
const EMPTY: ChatMessage[] = []

export type AskFailure = 'tooMany' | 'failed'

interface Options {
  route: Route
  scenario: Scenario
  /** Built when a question is sent, so it describes that moment: the plan now, the position now. */
  context: () => { plan: PlanContext | null; live: LiveContext | null }
}

function newId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

/** The earlier exchanges worth sending: answered ones only, most recent last. */
function historyOf(messages: ChatMessage[]): AskTurn[] {
  const turns: AskTurn[] = []
  for (let i = 1; i < messages.length; i++) {
    const [question, answer] = [messages[i - 1], messages[i]]
    if (question.role === 'user' && answer.role === 'assistant' && answer.reason === 'ok' && question.text && answer.text) {
      turns.push({ question: question.text, answer: answer.text })
    }
  }
  return turns.slice(-HISTORY_TURNS)
}

/** The conversation with the model about this route on the planned day, kept on the device. */
export function useAsk({ route, scenario, context }: Options) {
  const { lang } = useT()
  const date = usePlan((s) => s.date)
  const key = conversationKey(route.id, date)
  const messages = usePlan((s) => s.conversations[key]) ?? EMPTY
  const addMessage = usePlan((s) => s.addMessage)
  const clearConversation = usePlan((s) => s.clearConversation)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<AskFailure | null>(null)

  const send = async (raw: string) => {
    const question = raw.trim().slice(0, 300)
    if (!question || pending) return
    const history = historyOf(messages)
    addMessage(key, { id: newId(), role: 'user', at: Date.now(), text: question })
    setPending(true)
    setFailure(null)
    try {
      const { plan, live } = context()
      // Times computed at a pace factor are fractional; the wire carries whole minutes.
      if (plan) {
        plan.start = Math.round(plan.start)
        plan.turnaround = Math.round(plan.turnaround)
        plan.arrivals = Object.fromEntries(Object.entries(plan.arrivals).map(([id, at]) => [id, Math.round(at)]))
      }
      const answer = await askRoute(route.id, scenario, date, lang, { question, history, plan, live })
      addMessage(key, {
        id: newId(),
        role: 'assistant',
        at: Date.now(),
        text: answer.text,
        reason: answer.reason,
        model: answer.model,
        citations: answer.citations,
      })
    } catch (error) {
      setFailure(error instanceof ApiError && error.status === 429 ? 'tooMany' : 'failed')
    } finally {
      setPending(false)
    }
  }

  return { messages, pending, failure, send, clear: () => clearConversation(key) }
}

export type AskState = ReturnType<typeof useAsk>
