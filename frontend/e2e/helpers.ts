import { expect, type Page } from '@playwright/test'
import { ROUTE_ID } from './api'

/** Seeds the persisted plan store with the stubbed route and `patch`, then opens `path`. */
export async function withPlan(page: Page, path: string, patch: Record<string, unknown>) {
  await page.goto('/routes/new')
  await page.evaluate((patch) => {
    const stored = JSON.parse(localStorage.getItem('hsa-plan') ?? '{"state":{},"version":4}')
    stored.state = { ...stored.state, ...patch }
    stored.version = 4
    localStorage.setItem('hsa-plan', JSON.stringify(stored))
  }, { routeId: ROUTE_ID, ...patch })
  await page.goto(path)
}

/** Fails the test on any uncaught error or console error, except the expected 4xx a test provokes. */
export function watchConsole(page: Page, allow: RegExp[] = []) {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(String(error)))
  page.on('console', (message) => {
    if (message.type() === 'error' && !allow.some((pattern) => pattern.test(message.text()))) errors.push(message.text())
  })
  return () => expect(errors).toEqual([])
}

/**
 * Oeschinensee to the Blüemlisalphütte through the route picker, as a hiker plans it. Lands on the plan.
 * The hut by its full name: the gazetteer's first "Blüemlisalp" is a hamlet near Zürich, with no trail to it.
 */
export async function pickRoute(page: Page) {
  await page.goto('/routes/new')
  await page.getByLabel('From').fill('Oeschinensee')
  await page.getByRole('button', { name: /Oeschinensee/ }).first().click()
  await page.getByLabel('To').fill('Blüemlisalphütte')
  await page.getByRole('button', { name: /Blüemlisalphütte/ }).first().click()
  await page.getByRole('button', { name: 'Find route' }).click()
  await expect(page).toHaveURL(/\/($|\?|briefing)/, { timeout: 60_000 })
}

/** The route the persisted plan is on. */
export function plannedRouteId(page: Page): Promise<string> {
  return page.evaluate(() => JSON.parse(localStorage.getItem('hsa-plan') ?? '{}').state?.routeId)
}
