import { expect, type Page } from '@playwright/test'

/** Seeds the persisted plan store, then opens `path`. */
export async function withPlan(page: Page, path: string, patch: Record<string, unknown>) {
  await page.goto('/')
  await page.evaluate((patch) => {
    const stored = JSON.parse(localStorage.getItem('hsa-plan') ?? '{"state":{},"version":3}')
    stored.state = { ...stored.state, ...patch }
    stored.version = 3
    localStorage.setItem('hsa-plan', JSON.stringify(stored))
  }, patch)
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
