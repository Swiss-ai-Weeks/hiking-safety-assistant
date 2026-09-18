import { expect, test } from '@playwright/test'
import { stubApi } from './api'
import { watchConsole } from './helpers'

test.describe('the route picker @stubbed', () => {
  test('a suggested route fills both ends, and Find route builds it', async ({ page }) => {
    const clean = watchConsole(page)
    await stubApi(page)
    await page.goto('/routes/new')

    await expect(page.getByRole('button', { name: 'Find route' })).toBeDisabled()
    await page.getByRole('button', { name: /Oeschinensee → Blüemlisalphütte/ }).click()
    await expect(page.getByText('See Oeschinensee (BE) - Kandersteg')).toBeVisible()
    await expect(page.getByText('Gebaeude Blüemlisalphütte SAC (BE) - Kandersteg')).toBeVisible()

    await page.getByRole('button', { name: 'Find route' }).click()
    await expect(page).toHaveURL(/\/($|\?)/)
    clean()
  })
})
