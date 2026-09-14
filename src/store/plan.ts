import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { oeschinenRoute, routes } from '../data/mock/route-oeschinensee'
import type { CloudAnswer, Lang, Minutes, PaceAnswer, SavedPlan, Scenario } from '../domain/types'

export function nextSaturdayISO(from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  d.setDate(d.getDate() + ((6 - d.getDay() + 7) % 7 || 7))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const DEFAULT_START: Minutes = 7 * 60 + 30

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
  turnaround: Minutes
  groupSize: number
  hikeStarted: boolean
  hikeStartedAt: number | null
  cloudObservation: { answer: CloudAnswer; at: number } | null
  saved: SavedPlan[]
}

interface PlanActions {
  setLang: (lang: Lang) => void
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
  savePlan: () => void
  reopenPlan: (plan: SavedPlan) => void
  resetDemo: () => void
}

export type PlanState = PlanData & PlanActions

const initialData = (): PlanData => ({
  lang: 'en',
  scenario: 'assessed',
  routeId: oeschinenRoute.id,
  date: nextSaturdayISO(),
  originalStart: DEFAULT_START,
  start: DEFAULT_START,
  paceAnswer: null,
  planAccepted: false,
  turnaround: oeschinenRoute.turnaroundDefault,
  groupSize: 4,
  hikeStarted: false,
  hikeStartedAt: null,
  cloudObservation: null,
  saved: [],
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
        savePlan: () => {
          const { routeId, date, start, saved } = get()
          const route = routes[routeId]
          const plan: SavedPlan = {
            id: `${routeId}-${date}-${start}`,
            routeId,
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
        resetDemo: () => set({ ...initialData(), lang: get().lang }),
      }
    },
    { name: 'hsa-plan', version: 1 },
  ),
)

export function useRoute() {
  const routeId = usePlan((s) => s.routeId)
  return routes[routeId] ?? oeschinenRoute
}
