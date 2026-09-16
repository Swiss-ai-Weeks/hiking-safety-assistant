import { useSuspenseQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { assessmentQuery } from '../api/queries'
import { evaluate } from '../domain/assessment'
import { computeArrivals } from '../domain/timing'
import { resolveScenario } from '../lib/scenario'
import { usePlan, useRoute } from '../store/plan'

/** Everything the assessment, map and share screens derive from the plan. */
export function useAssessmentView() {
  const route = useRoute()
  const start = usePlan((s) => s.start)
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const storedScenario = usePlan((s) => s.scenario)
  const date = usePlan((s) => s.date)
  const [params] = useSearchParams()

  const scenario = resolveScenario(storedScenario, params)
  const { data } = useSuspenseQuery(assessmentQuery(route.id, scenario, date))
  const arrivals = useMemo(() => computeArrivals(route, start, paceAnswer), [route, start, paceAnswer])
  const evaluation = useMemo(() => evaluate(route, arrivals, data), [route, arrivals, data])

  /** Scenario overrides to carry across links. */
  const search = useMemo(() => {
    const keep = new URLSearchParams()
    for (const key of ['outcome', 'stale']) {
      const value = params.get(key)
      if (value) keep.set(key, value)
    }
    const s = keep.toString()
    return s ? `?${s}` : ''
  }, [params])

  return { route, start, paceAnswer, scenario, data, arrivals, evaluation, search, params }
}

export type AssessmentView = ReturnType<typeof useAssessmentView>
