import type { Page, Route as Request } from '@playwright/test'
import type { Answer, AssessmentData, Narration, PlaceResult } from '../src/domain/types'
import { getAssessmentData, type Scenario } from '../src/test/fixtures/mockApi'
import { oeschinenRoute } from '../src/test/fixtures/route-oeschinensee'

/** The id the stubbed API knows. Seed it with `withPlan` to open a screen on it. */
export const ROUTE_ID = oeschinenRoute.id

/**
 * Answers the app's API calls in the browser, from the test fixtures.
 *
 * The backend serves real data only, and real routing and forecasts cannot be pinned for a test. So
 * these specs check the frontend in each state it renders, over fixed data, and never touch a source.
 * Tagged @stubbed; `E2E_BASE_URL` runs the others against a real server instead.
 */
export async function stubApi(page: Page, scenario: Scenario = 'assessed') {
  const assessment: AssessmentData = getAssessmentData(scenario)

  await page.route('**/api/**', async (request: Request) => {
    const url = new URL(request.request().url())
    const path = url.pathname.replace(/^\/api/, '')
    const method = request.request().method()
    const json = (body: unknown, status = 200) => request.fulfill({ status, json: body })

    if (path === '/routes/search') {
      const needle = (url.searchParams.get('q') ?? '').toLocaleLowerCase()
      const places: PlaceResult[] = oeschinenRoute.waypoints
        .filter((waypoint) => needle && waypoint.name.toLocaleLowerCase().includes(needle))
        .map((waypoint, rank) => ({ name: waypoint.name, latLng: waypoint.latLng, rank }))
      return json(places)
    }
    if (path === '/routes' && method === 'POST') return json(oeschinenRoute)
    if (path === '/forecast/retry') return json({ available: false, checkedAt: 8 * 60 + 12 })

    const match = path.match(/^\/routes\/([^/]+)(\/\w+)?$/)
    if (!match || decodeURIComponent(match[1]) !== ROUTE_ID) {
      return json({ detail: 'Unknown route', source: 'stub' }, 404)
    }
    switch (match[2]) {
      case undefined:
        return json(oeschinenRoute)
      case '/assessment':
        return json(assessment)
      case '/narration': {
        const narration: Narration = {
          enabled: false,
          hazards: assessment.hazards.map((hazard) => ({ id: hazard.id, citations: [] })),
        }
        return json(narration)
      }
      case '/ask': {
        const answer: Answer = { enabled: false, reason: 'disabled', citations: [] }
        return json(answer)
      }
    }
    return json({ detail: 'Not stubbed', source: 'stub' }, 404)
  })
}
