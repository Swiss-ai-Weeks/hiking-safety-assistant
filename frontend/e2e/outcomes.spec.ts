import { expect, test } from '@playwright/test'
import { stubApi } from './api'
import { pickRoute, plannedRouteId, watchConsole, withPlan } from './helpers'

test.describe('the briefing in each outcome state @stubbed', () => {
  test('assessed: the hazard check flags the showcase hazards, and the plan carries the rule', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page)
    await withPlan(page, '/briefing?step=4', { paceAnswer: '5to6' })

    await expect(page.getByText('Assessed', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /Wind gusts/ })).toBeVisible()
    await page.getByRole('button', { name: /Wind gusts/ }).click()
    await expect(page.getByRole('article')).toBeVisible()

    await page.goto('/briefing?step=5')
    await expect(page.getByText('Your turnaround rule')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start hike' })).toBeEnabled()
    clean()
  })

  test('partial: says which segments were not evaluated', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page, 'partial')
    await withPlan(page, '/briefing?step=4', { paceAnswer: '5to6' })

    await expect(page.getByText('Partially assessed')).toBeVisible()
    await expect(page.getByText(/^Not evaluated:/)).toBeVisible()
    clean()
  })

  test('not assessable: the story stops at the weather, with the official sources and a retry', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page, 'not_assessable')
    await withPlan(page, '/briefing?step=4', {})

    await expect(page.getByText("We can't assess this hike right now.")).toBeVisible()
    await expect(page.getByRole('link', { name: 'MeteoSwiss forecast' })).toBeVisible()
    const retry = page.waitForRequest((request) => request.url().includes('/api/forecast/retry'))
    await page.getByRole('button', { name: 'Try again' }).click()
    await retry
    clean()
  })

  test('stale: the forecast age is shown', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page, 'stale')
    await withPlan(page, '/briefing?step=4', { paceAnswer: '5to6' })

    await expect(page.getByText(/h old/)).toBeVisible()
    clean()
  })
})

test.describe('asking about the hike', () => {
  test('the briefing opens the conversation, and says when no model is set up @stubbed', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page)
    await withPlan(page, '/briefing?step=1', {})

    const open = page.getByRole('button', { name: 'Ask' })
    await expect(open).toBeInViewport()
    await open.click()
    const composer = page.getByRole('textbox', { name: /Ask Nemotron/ })
    await expect(composer).toBeInViewport()
    await composer.fill('When is it windiest at Hohtürli?')
    await composer.press('Enter')

    await expect(page.getByRole('heading', { name: 'Ask Nemotron' })).toBeVisible()
    await expect(page.getByText('When is it windiest at Hohtürli?')).toBeVisible()
    await expect(page.getByText(/none is set up on this server/)).toBeVisible()
    await page.getByRole('button', { name: 'Back to the briefing' }).click()
    await expect(page.getByRole('heading', { name: 'The route' })).toBeVisible()
    clean()
  })

  test('a live answer is marked as the model’s, with figures filled in', async ({ page }) => {
    test.skip(!process.env.E2E_BASE_URL, 'needs a server with a model')
    const clean = watchConsole(page)
    // A real server has no built-in route: plan one the way a hiker does.
    await pickRoute(page)
    await withPlan(page, '/briefing?step=1', { paceAnswer: '5to6', routeId: await plannedRouteId(page) })

    await page.getByRole('button', { name: 'Ask' }).click()
    const composer = page.getByRole('textbox', { name: /Ask Nemotron/ })
    await composer.fill('Which section is the most exposed?')
    await composer.press('Enter')

    const answer = page.getByRole('note', { name: /Worded by Nemotron/ }).last()
    await expect(answer).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/\{[\w.-]+\}/)).toHaveCount(0)
    clean()
  })
})

test('picking a route from search opens its briefing @stubbed', async ({ page }) => {
  const clean = watchConsole(page)
  await stubApi(page)
  await pickRoute(page)
  clean()
})

test.describe('with no route planned @stubbed', () => {
  test('a first visit opens on route search, with Settings in reach', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page)
    await page.goto('/briefing')

    await expect(page).toHaveURL(/\/routes\/new$/)
    await expect(page.getByRole('link', { name: 'Back' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
    clean()
  })

  test('a device still on the retired demo route is sent to search, not to a 404', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page)
    await page.goto('/routes/new')
    await page.evaluate(() => {
      const state = { routeId: 'oeschinensee-bluemlisalphuette', scenario: 'partial', hikeStarted: true, saved: [], recentRoutes: [] }
      localStorage.setItem('hsa-plan', JSON.stringify({ state, version: 3 }))
    })
    await page.goto('/field')

    await expect(page).toHaveURL(/\/routes\/new$/)
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('hsa-plan') ?? '{}'))
    expect(stored.version).toBe(4)
    expect(stored.state.routeId).toBeNull()
    expect(stored.state.hikeStarted).toBe(false)
    expect(stored.state).not.toHaveProperty('scenario')
    clean()
  })
})
