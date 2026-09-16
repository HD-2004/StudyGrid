import { expect, test } from '@playwright/test'

test('analyzes material, builds a plan, and adapts after recall feedback', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })
  page.on('pageerror', (error) => browserErrors.push(error.message))

  await page.goto('/')
  await page.locator('.empty-calendar-overlay .material-tonal-button').click()
  await expect(page.getByRole('heading', { name: 'Create study plan' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Build around your real week' })).toBeVisible()

  await page.getByRole('button', { name: 'Analyze material' }).first().click()
  await expect(page.getByText(/topics extracted/i).first()).toBeVisible()

  await page.getByRole('button', { name: 'Generate study plan' }).click()
  const invalidFields = await page.locator('input:invalid, select:invalid, textarea:invalid').evaluateAll(
    (elements) =>
      elements.map((element) => ({
        tag: element.tagName,
        name: element.getAttribute('aria-label') || element.getAttribute('name'),
        value: (element as HTMLInputElement).value,
        message: (element as HTMLInputElement).validationMessage,
      })),
  )
  expect(invalidFields, JSON.stringify(invalidFields)).toEqual([])
  await expect(page.locator('.sx__event').first()).toBeVisible()

  await page.locator('.sx__event').first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('How did this session go?')).toBeVisible()
  await dialog.getByText('Very little').click()
  await dialog.getByRole('button', { name: 'Save progress' }).click()

  await expect(page.getByRole('heading', { name: 'Your plan adapted' })).toBeVisible()
  await page.screenshot({ path: 'test-results/studygrid-plan.png', fullPage: true })

  expect(browserErrors).toEqual([])
})

test('fits a mobile viewport and supports dark mode', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Create your study schedule' })).toBeVisible()
  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.locator('.empty-calendar-overlay .material-tonal-button').click()
  await expect(page.getByRole('heading', { name: 'Create study plan' })).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(hasHorizontalOverflow).toBe(false)
  await page.screenshot({ path: 'test-results/studygrid-mobile-dark.png' })
})

test('calendar is interactive on load and the setup drawer can close and reopen', async ({ page }) => {
  await page.goto('/')

  const shell = page.locator('main.app-shell')
  const drawer = page.getByRole('dialog', { name: 'Create study plan' })

  await expect(drawer).toHaveCount(0)
  await expect(shell).not.toHaveAttribute('inert', '')

  await page.locator('.empty-calendar-overlay .material-tonal-button').click()
  await expect(drawer).toBeVisible()
  await expect(shell).toHaveAttribute('inert', '')

  await drawer.getByRole('button', { name: 'Close plan setup' }).click()
  await expect(drawer).toHaveCount(0)
  await expect(shell).not.toHaveAttribute('inert', '')

  await page.locator('.menu-button').click()
  await expect(drawer).toBeVisible()
  await page.locator('.planner-scrim').click()
  await expect(drawer).toHaveCount(0)
})
