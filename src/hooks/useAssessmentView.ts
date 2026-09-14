import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { getAssessmentData, resolveScenario } from '../data/mock/mockApi'
import { evaluate } from '../domain/assessment'
import { computeArrivals } from '../domain/timing'
import { usePlan, useRoute } from '../store/plan'

/** Everything the assessment, map and share screens derive from the plan. */
export function useAssessmentView() {
  const route = useRoute()
  const start = usePlan((s) => s.start)
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const storedScenario = usePlan((s) => s.scenario)
  const [params] = useSearchParams()

  const scenario = resolveScenario(storedScenario, params)
  const data = useMemo(() => getAssessmentData(scenario), [scenario])
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
