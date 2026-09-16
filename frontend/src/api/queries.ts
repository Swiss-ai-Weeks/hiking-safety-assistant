import { queryOptions } from '@tanstack/react-query'
import type { AssessmentData, Minutes, PlaceResult, Route, RouteRequest, Scenario } from '../domain/types'
import { api } from './client'

export const routeQuery = (routeId: string) =>
  queryOptions({
    queryKey: ['route', routeId],
    queryFn: () => api<Route>(`/routes/${encodeURIComponent(routeId)}`),
  })

/** Hazards for the hike on `date` (YYYY-MM-DD). Severity is resolved client-side at arrival. */
export const assessmentQuery = (routeId: string, scenario: Scenario, date: string) =>
  queryOptions({
    queryKey: ['assessment', routeId, scenario, date],
    queryFn: () =>
      api<AssessmentData>(
        `/routes/${encodeURIComponent(routeId)}/assessment?scenario=${scenario}&date=${encodeURIComponent(date)}`,
      ),
  })

/** "Try again" on the not-assessable screen: asks the forecast source whether it answers now. */
export function retryForecast(date: string) {
  return api<{ available: boolean; checkedAt: Minutes }>(`/forecast/retry?date=${encodeURIComponent(date)}`, {
    method: 'POST',
  })
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
