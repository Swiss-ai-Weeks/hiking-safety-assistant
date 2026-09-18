import { useSuspenseQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { assessmentQuery } from '../api/queries'
import { evaluate } from '../domain/assessment'
import { computeArrivals } from '../domain/timing'
import { usePlan, useRoute } from '../store/plan'

/** Everything the assessment, map and share screens derive from the plan. */
export function useAssessmentView() {
  const route = useRoute()
  const start = usePlan((s) => s.start)
  const paceAnswer = usePlan((s) => s.paceAnswer)
  const date = usePlan((s) => s.date)

  const { data } = useSuspenseQuery(assessmentQuery(route.id, date))
  const arrivals = useMemo(() => computeArrivals(route, start, paceAnswer), [route, start, paceAnswer])
  const evaluation = useMemo(() => evaluate(route, arrivals, data), [route, arrivals, data])

  return { route, start, paceAnswer, data, arrivals, evaluation }
}

export type AssessmentView = ReturnType<typeof useAssessmentView>
