import { queryOptions } from '@tanstack/react-query'
import type {
  Answer,
  AskRequest,
  AssessmentData,
  Lang,
  Minutes,
  Narration,
  PlaceResult,
  Route,
  RouteRequest,
} from '../domain/types'
import { api } from './client'

export const routeQuery = (routeId: string) =>
  queryOptions({
    queryKey: ['route', routeId],
    queryFn: () => api<Route>(`/routes/${encodeURIComponent(routeId)}`),
  })

/** How long an assessment is trusted before it is fetched again: about as often as a new model run is looked for. */
const FORECAST_STALE_MS = 10 * 60_000

/**
 * Hazards for the hike on `date` (YYYY-MM-DD). Severity is resolved client-side at arrival.
 *
 * Refetched in the background once `FORECAST_STALE_MS` old, on focus or a new mount, so a briefing
 * left open (or a phone taken out on the trail) picks up a newer forecast run.
 */
export const assessmentQuery = (routeId: string, date: string) =>
  queryOptions({
    queryKey: ['assessment', routeId, date],
    queryFn: () => api<AssessmentData>(`/routes/${encodeURIComponent(routeId)}/assessment?date=${encodeURIComponent(date)}`),
    staleTime: FORECAST_STALE_MS,
  })

/**
 * The same hazards phrased by a language model, with the guidance each is grounded in.
 *
 * Never on the critical path: the cards render from the assessment and its templates first, and a
 * failed or slow narration leaves them as they are. Not retried, for the same reason.
 */
export const narrationQuery = (routeId: string, date: string, lang: Lang) =>
  queryOptions({
    queryKey: ['narration', routeId, date, lang],
    queryFn: () =>
      api<Narration>(`/routes/${encodeURIComponent(routeId)}/narration?date=${encodeURIComponent(date)}&lang=${lang}`),
    retry: false,
    staleTime: 5 * 60_000,
  })

/**
 * A question about the hike, answered by the language model from the assessment and the plan. Never
 * throws on the model's account: `reason` says why there is no text. A 429 means too many questions.
 */
export function askRoute(routeId: string, date: string, lang: Lang, body: AskRequest) {
  return api<Answer>(
    `/routes/${encodeURIComponent(routeId)}/ask?date=${encodeURIComponent(date)}&lang=${lang}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
  )
}

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
