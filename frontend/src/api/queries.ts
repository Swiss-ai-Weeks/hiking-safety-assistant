import { queryOptions } from '@tanstack/react-query'
import type { AssessmentData, Minutes, PlaceResult, RecentRoute, Route, RouteRequest, Scenario } from '../domain/types'
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

/** Place-name search for the ends of a route. Disabled until there is something to search for. */
export const placeSearchQuery = (query: string) =>
  queryOptions({
    queryKey: ['places', query],
    queryFn: () => api<PlaceResult[]>(`/routes/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 1,
  })

/**
 * Route two searched places over the official network.
 *
 * The id it returns is deterministic, so posting the same pair twice is idempotent and the
 * result is immediately fetchable with `routeQuery`.
 */
export function createRoute(request: RouteRequest) {
  return api<Route>('/routes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}
