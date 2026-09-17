import { expect, test } from '@playwright/test'
import { watchConsole, withPlan } from './helpers'

// Between Oberbärgli and the moraine on the demo route.
const ON_ROUTE = { latitude: 46.4955, longitude: 7.7512 }

test.use({ geolocation: ON_ROUTE, permissions: ['geolocation'], viewport: { width: 390, height: 844 } })

async function startHike(page: import('@playwright/test').Page, hoursAgo = 1) {
  await withPlan(page, '/field', {
    paceAnswer: '5to6',
    planAccepted: true,
    hikeStarted: true,
    hikeStartedAt: Date.now() - hoursAgo * 3600_000,
    cloudObservation: null,
  })
}

test.describe('field mode @demo', () => {
  test('the map, the three numbers, SOS and the composer are on one screen', async ({ page }) => {
    const clean = watchConsole(page)
    await startHike(page)

    await expect(page.locator('.leaflet-container')).toBeVisible()
    await expect(page.locator('.map-walker')).toBeVisible()
    for (const label of ['Next', 'Left', 'ETA']) await expect(page.getByText(label, { exact: true })).toBeInViewport()
    await expect(page.getByRole('link', { name: 'Emergency 1414' })).toBeInViewport()
    await expect(page.getByRole('textbox', { name: /Ask Nemotron/ })).toBeInViewport()
    await page.screenshot({ path: 'test-results/field-peek.png' })
    clean()
  })

  test('cloud below the ridge is the rule saying turn', async ({ page }) => {
    const clean = watchConsole(page)
    await startHike(page)

    await page.getByRole('button', { name: 'Below the ridge' }).click()

    await expect(page.getByRole('alert').filter({ hasText: 'Your rule says turn. Descend via Oberbärgli.' })).toBeVisible()
    await expect(page.getByText(/Noted at \d\d:\d\d: Below the ridge/)).toBeVisible()
    clean()
  })

  test('typing a question opens the conversation', async ({ page }) => {
    const clean = watchConsole(page)
    await startHike(page)

    const composer = page.getByRole('textbox', { name: /Ask Nemotron/ })
    await composer.fill('How long to Hohtürli?')
    await composer.press('Enter')

    await expect(page.getByRole('button', { name: 'Hide conversation' })).toBeVisible()
    await expect(page.getByText('Your plan', { exact: true })).toBeVisible()
    await expect(page.getByText(/none is set up on this server/)).toBeVisible()
    await page.screenshot({ path: 'test-results/field-conversation.png' })
    clean()
  })

  test('ending the hike asks first', async ({ page }) => {
    const clean = watchConsole(page)
    await startHike(page)

    await page.getByRole('button', { name: 'More' }).click()
    await page.getByRole('button', { name: 'End hike' }).click()
    await expect(page.getByRole('alertdialog')).toContainText('End this hike?')
    await page.getByRole('alertdialog').getByRole('button', { name: 'End hike' }).click()

    await expect(page).toHaveURL(/\/$/)
    clean()
  })
})
