import { useSuspenseQuery } from '@tanstack/react-query'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { routeQuery } from '../api/queries'
import type { ChatMessage, CloudAnswer, Lang, Minutes, PaceAnswer, RecentRoute, Route, SavedPlan, Scenario } from '../domain/types'

export function nextSaturdayISO(from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  d.setDate(d.getDate() + ((6 - d.getDay() + 7) % 7 || 7))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * The demo route, and what the app falls back to.
 *
 * A computed route's id is a digest of the search that made it, and the backend holds that route
 * in its disk cache for thirty days. An id saved for longer than that resolves to a 404 — and
 * since the route is read with `useSuspenseQuery`, that throws on every screen. `LoadBoundary`
 * recognises the 404 and offers this route, which cannot expire, as the way back.
 */
export const DEFAULT_ROUTE_ID = 'oeschinensee-bluemlisalphuette'
const DEFAULT_START: Minutes = 7 * 60 + 30
const MAX_RECENT = 5
/** Messages kept per conversation, and conversations kept on the device. */
const MAX_MESSAGES = 40
const MAX_CONVERSATIONS = 10

/** One conversation per route and day: a question about Saturday means nothing on Sunday. */
export function conversationKey(routeId: string, date: string): string {
  return `${routeId}|${date}`
}

interface PlanData {
  lang: Lang
  scenario: Scenario
  routeId: string
  date: string
  /** Start time chosen on the Plan screen. */
  originalStart: Minutes
  /** Current start time (may be moved by a suggestion or "Adjust"). */
  start: Minutes
  paceAnswer: PaceAnswer | null
  planAccepted: boolean
  /** `null` until adjusted: use the route's default (see `useTurnaround`). */
  turnaround: Minutes | null
  groupSize: number
  hikeStarted: boolean
  hikeStartedAt: number | null
  cloudObservation: { answer: CloudAnswer; at: number } | null
  saved: SavedPlan[]
  /** Routes picked on this device, most recent first. The server keeps no history. */
  recentRoutes: RecentRoute[]
  /** Questions to the model and its answers, by `conversationKey`. Only on this device. */
  conversations: Record<string, ChatMessage[]>
}

interface PlanActions {
  setLang: (lang: Lang) => void
  setRouteId: (routeId: string) => void
  /** Plan `route` and remember it under Recent. */
  openRoute: (route: Pick<Route, 'id' | 'fromName' | 'toName' | 'grade'>) => void
  setScenario: (scenario: Scenario) => void
  setDate: (date: string) => void
  setPlannedStart: (start: Minutes) => void
  checkConditions: () => void
  setStart: (start: Minutes) => void
  setPaceAnswer: (answer: PaceAnswer) => void
  acceptPlan: () => void
  setTurnaround: (turnaround: Minutes) => void
  setGroupSize: (size: number) => void
  startHike: () => void
  endHike: () => void
  observeCloud: (answer: CloudAnswer) => void
  savePlan: (route: Route) => void
  reopenPlan: (plan: SavedPlan) => void
  addMessage: (key: string, message: ChatMessage) => void
  clearConversation: (key: string) => void
  resetDemo: () => void
}

export type PlanState = PlanData & PlanActions

const initialData = (): PlanData => ({
  lang: 'en',
  scenario: 'assessed',
  routeId: DEFAULT_ROUTE_ID,
  date: nextSaturdayISO(),
  originalStart: DEFAULT_START,
  start: DEFAULT_START,
  paceAnswer: null,
  planAccepted: false,
  turnaround: null,
  groupSize: 4,
  hikeStarted: false,
  hikeStartedAt: null,
  cloudObservation: null,
  saved: [],
  recentRoutes: [],
  conversations: {},
})

export const usePlan = create<PlanState>()(
  persist(
    (set, get) => {
      /** Forgiveness: plan inputs stay editable until "Start hike". */
      const edit = (patch: Partial<PlanData>) => {
        if (!get().hikeStarted) set(patch)
      }

      return {
        ...initialData(),
        setLang: (lang) => set({ lang }),
        setRouteId: (routeId) => edit({ routeId, planAccepted: false, turnaround: null }),
        openRoute: (route) => {
          if (get().hikeStarted) return
          const recent: RecentRoute = {
            id: route.id,
            name: `${route.fromName} → ${route.toName}`,
            grade: route.grade,
            usedAt: Date.now(),
          }
          set({
            routeId: route.id,
            planAccepted: false,
            turnaround: null,
            recentRoutes: [recent, ...get().recentRoutes.filter((r) => r.id !== route.id)].slice(0, MAX_RECENT),
          })
        },
        setScenario: (scenario) => set({ scenario }),
        setDate: (date) => edit({ date }),
        setPlannedStart: (start) => edit({ start, originalStart: start }),
        checkConditions: () => edit({ originalStart: get().start }),
        setStart: (start) => edit({ start }),
        setPaceAnswer: (paceAnswer) => edit({ paceAnswer }),
        acceptPlan: () => edit({ planAccepted: true }),
        setTurnaround: (turnaround) => edit({ turnaround }),
        setGroupSize: (groupSize) => edit({ groupSize: Math.min(12, Math.max(2, groupSize)) }),
        startHike: () => {
          const { paceAnswer, planAccepted, hikeStarted } = get()
          if (!paceAnswer || !planAccepted || hikeStarted) return
          set({ hikeStarted: true, hikeStartedAt: Date.now(), cloudObservation: null })
        },
        endHike: () => set({ hikeStarted: false, hikeStartedAt: null, planAccepted: false, cloudObservation: null }),
        observeCloud: (answer) => set({ cloudObservation: { answer, at: Date.now() } }),
        savePlan: (route) => {
          const { date, start, saved } = get()
          const plan: SavedPlan = {
            id: `${route.id}-${date}-${start}`,
            routeId: route.id,
            routeName: `${route.fromName} → ${route.toName}`,
            grade: route.grade,
            date,
            start,
            savedAt: Date.now(),
          }
          set({ saved: [plan, ...saved.filter((p) => p.id !== plan.id)].slice(0, 5) })
        },
        reopenPlan: (plan) =>
          edit({ routeId: plan.routeId, date: plan.date, start: plan.start, originalStart: plan.start, planAccepted: false }),
        addMessage: (key, message) => {
          const conversations = { ...get().conversations }
          conversations[key] = [...(conversations[key] ?? []), message].slice(-MAX_MESSAGES)
          // Keep the most recently used conversations: the key just written moves to the end.
          const { [key]: current, ...rest } = conversations
          const kept = Object.entries(rest).slice(-(MAX_CONVERSATIONS - 1))
          set({ conversations: { ...Object.fromEntries(kept), [key]: current } })
        },
        clearConversation: (key) => {
          set({ conversations: Object.fromEntries(Object.entries(get().conversations).filter(([k]) => k !== key)) })
        },
        resetDemo: () => set({ ...initialData(), lang: get().lang }),
      }
    },
    {
      name: 'hsa-plan',
      version: 3,
      // v2 keeps recent routes on the device, now that the server no longer invents a list.
      // v3 keeps the conversation with the model about each hike.
      migrate: (persisted, version) => {
        let state = persisted as Partial<PlanData>
        if (version < 2) state = { ...state, recentRoutes: [] }
        if (version < 3) state = { ...state, conversations: {} }
        return state
      },
    },
  ),
)

/** The planned route, fetched from the backend. Suspends until loaded. */
export function useRoute(): Route {
  const routeId = usePlan((s) => s.routeId)
  return useSuspenseQuery(routeQuery(routeId)).data
}

export function useTurnaround(): Minutes {
  const route = useRoute()
  const turnaround = usePlan((s) => s.turnaround)
  return turnaround ?? route.turnaroundDefault
}
