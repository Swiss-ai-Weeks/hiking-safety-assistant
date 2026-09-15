import { queryOptions } from '@tanstack/react-query'
import type { AssessmentData, Minutes, RecentRoute, Route, Scenario } from '../domain/types'
import { api } from './client'

export const routeQuery = (routeId: string) =>
  queryOptions({
    queryKey: ['route', routeId],
    queryFn: () => api<Route>(`/routes/${encodeURIComponent(routeId)}`),
  })

export const recentRoutesQuery = queryOptions({
  queryKey: ['recent-routes'],
  queryFn: () => api<RecentRoute[]>('/recent-routes'),
})

export const assessmentQuery = (routeId: string, scenario: Scenario) =>
  queryOptions({
    queryKey: ['assessment', routeId, scenario],
    queryFn: () => api<AssessmentData>(`/routes/${encodeURIComponent(routeId)}/assessment?scenario=${scenario}`),
  })

/** "Try again" on the not-assessable screen. */
export function retryForecast() {
  return api<{ available: boolean; checkedAt: Minutes }>('/forecast/retry', { method: 'POST' })
}
