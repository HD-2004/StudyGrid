import { expect, test, type Locator } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

function summarizeViolations(
  violations: Awaited<ReturnType<AxeBuilder['analyze']>>['violations'],
) {
  return violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    nodes: violation.nodes.map((node) => ({
      target: node.target,
      html: node.html,
      failure: node.failureSummary,
    })),
  }))
}

async function fillMinimalPlan(dialog: Locator) {
  await dialog.getByLabel('Subject').first().fill('Linear Algebra')
  await dialog.getByLabel('Topic 1 name').first().fill('Vector spaces')
}

test('analyzes real input, builds a plan, adapts it, and resets cleanly', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })
  page.on('pageerror', (error) => browserErrors.push(error.message))

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Create your study schedule' })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('main.app-shell')).not.toHaveAttribute('inert', '')

  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create study plan' })
  await expect(dialog).toBeVisible()
  await expect(page.locator('main.app-shell')).toHaveAttribute('inert', '')
  await fillMinimalPlan(dialog)

  const material = dialog.getByLabel('Or paste a syllabus, notes, or topic outline').first()
  await material.fill(`
    Vector spaces and linear combinations
    Matrix transformations and determinants
    Eigenvalues and eigenvectors
    Orthogonality and least squares
  `)
  await dialog.getByRole('button', { name: 'Analyze pasted text' }).first().click()
  await expect(dialog.getByText(/topics extracted and added below/i)).toBeVisible({ timeout: 30_000 })
  await expect(dialog.getByText(/OpenAI analysis|Offline fallback/)).toBeVisible()

  await dialog.getByRole('button', { name: 'Generate study plan' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('.sx__event').first()).toBeVisible()
  await expect(page.locator('.calendar-app')).toBeVisible()

  const calendarResults = await new AxeBuilder({ page })
    .include('.calendar-app')
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  expect(summarizeViolations(calendarResults.violations)).toEqual([])

  await page.locator('.sx__event').first().click()
  await expect(page.locator('.session-detail')).toBeVisible()
  await page.getByRole('button', { name: 'Completed', exact: true }).click()
  await page.getByLabel('Bạn nhớ nội dung ở mức nào?').selectOption('poor')
  await page.getByRole('button', { name: 'Xác nhận hoàn thành' }).click()

  await page.getByRole('button', { name: 'Tiến độ', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Where your week went' })).toBeVisible()
  await expect(page.getByText('Synced from study progress')).toBeVisible()

  await page.getByLabel('Category', { exact: true }).selectOption('unexpected')
  await page.getByLabel('Custom label').fill('Urgent family task')
  await page.getByLabel('Duration (minutes)').fill('90')
  await page.getByRole('button', { name: 'Log activity' }).click()
  await expect(page.getByText('Urgent family task')).toBeVisible()
  await page.getByRole('button', { name: '30 days' }).click()
  await expect(page.getByRole('heading', { name: 'Category totals (30 days)' })).toBeVisible()

  const progressResults = await new AxeBuilder({ page })
    .include('.progress-dashboard')
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  expect(summarizeViolations(progressResults.violations)).toEqual([])

  await page.setViewportSize({ width: 390, height: 844 })
  const progressOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(progressOverflow).toBe(false)
  await expect(page.locator('.progress-dashboard')).toBeVisible()
  await page.setViewportSize({ width: 1440, height: 1000 })

  await page.getByRole('button', { name: 'Return to calendar' }).click()
  await expect(page.locator('.calendar-app')).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.calendar-app')).toBeVisible()
  const calendarOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(calendarOverflow).toBe(false)
  await page.setViewportSize({ width: 1440, height: 1000 })

  await page.getByRole('button', { name: 'Tạo kế hoạch mới' }).click()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Close plan setup' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('.empty-calendar-overlay')).toBeVisible()

  expect(browserErrors).toEqual([])
})

test('supports dark mode, phone layout, and keyboard dismissal', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: 'Switch to light theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')

  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create study plan' })
  await expect(dialog).toBeVisible()

  await page.keyboard.press('Tab')
  const focusedTag = await page.evaluate(() => document.activeElement?.tagName)
  expect(focusedTag).not.toBe('BODY')

  const unlabeledFields = await dialog.locator('input, select, textarea').evaluateAll((elements) =>
    elements
      .filter((element) => {
        const id = element.getAttribute('id')
        const hasLabel = id ? Boolean(document.querySelector(`label[for="${id}"]`)) : false
        return !hasLabel && !element.getAttribute('aria-label') && !element.closest('label')
      })
      .map((element) => element.outerHTML),
  )
  expect(unlabeledFields).toEqual([])

  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(hasHorizontalOverflow).toBe(false)
})

test('keeps the empty calendar interactive while setup opens and closes', async ({ page }) => {
  await page.goto('/')

  const shell = page.locator('main.app-shell')
  const createButton = page
    .locator('.empty-calendar-overlay')
    .getByRole('button', { name: 'Create study plan' })

  await expect(shell).not.toHaveAttribute('inert', '')
  await expect(page.locator('.calendar')).toBeVisible()

  await createButton.click()
  const dialog = page.getByRole('dialog', { name: 'Create study plan' })
  await expect(dialog).toBeVisible()
  await expect(shell).toHaveAttribute('inert', '')

  await dialog.getByRole('button', { name: 'Close plan setup' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(shell).not.toHaveAttribute('inert', '')
  await expect(createButton).toBeFocused()
})

test('restores an owned plan after reload and deletes all session data on request', async ({ page }) => {
  await page.goto('/')
  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create study plan' })
  await fillMinimalPlan(dialog)
  await dialog.getByRole('button', { name: 'Generate study plan' }).click()
  await expect(page.locator('.sx__event').first()).toBeVisible()
  const countBeforeReload = await page.locator('.sx__event').count()

  await page.reload()
  await expect(page.locator('.sx__event').first()).toBeVisible()
  await expect(page.locator('.sx__event')).toHaveCount(countBeforeReload)
  await expect(page.getByRole('button', { name: 'Xóa dữ liệu của tôi' })).toBeVisible()

  await page.getByRole('button', { name: 'Xóa dữ liệu của tôi' }).click()
  await page.getByRole('button', { name: 'Xác nhận xóa dữ liệu' }).click()
  await expect(page.locator('.empty-calendar-overlay')).toBeVisible()

  await page.reload()
  await expect(
    page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }),
  ).toBeVisible()
})

test('creates a pending task, cancels with a reason, reschedules, and updates progress', async ({ page }) => {
  await page.goto('/')
  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const setup = page.getByRole('dialog', { name: 'Create study plan' })
  await fillMinimalPlan(setup)
  await setup.getByRole('button', { name: 'Generate study plan' }).click()
  await expect(page.locator('.calendar-app')).toBeVisible()

  await page.getByRole('button', { name: 'Tạo', exact: true }).click()
  const createDialog = page.getByRole('dialog', { name: 'Thêm vào lịch' })
  await createDialog.getByLabel('Tên công việc').fill('Demo rehearsal')
  await createDialog.getByLabel('Lịch / nhóm').fill('Capstone')
  await createDialog.getByLabel('Bắt đầu').fill('2026-09-17T18:00')
  await createDialog.getByLabel('Kết thúc').fill('2026-09-17T19:00')
  await createDialog.getByRole('button', { name: 'Tạo công việc' }).click()

  const manualEvent = page.getByRole('button', { name: /Capstone: Demo rehearsal/ })
  await expect(manualEvent).toBeVisible()
  const eventBox = await manualEvent.boundingBox()
  expect(eventBox).not.toBeNull()
  await page.mouse.move(eventBox!.x + eventBox!.width / 2, eventBox!.y + 12)
  await page.mouse.down()
  await page.mouse.move(eventBox!.x + eventBox!.width / 2, eventBox!.y + 40, { steps: 4 })
  await page.mouse.up()
  await expect(manualEvent).toHaveAttribute('aria-label', /18:30.*19:30/)

  const resizeHandle = manualEvent.locator('.resize-handle')
  const handleBox = await resizeHandle.boundingBox()
  expect(handleBox).not.toBeNull()
  await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + 2)
  await page.mouse.down()
  await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + 30, { steps: 4 })
  await page.mouse.up()
  await expect(manualEvent).toHaveAttribute('aria-label', /18:30.*20:00/)

  await manualEvent.click()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByText('Vì sao bạn hủy công việc này?')).toBeVisible()
  await page.getByRole('button', { name: 'Unexpected work' }).click()
  await page.getByRole('button', { name: 'Xác nhận & dời lịch' }).click()
  await expect(page.locator('.session-detail')).toHaveCount(0)

  await page.getByRole('button', { name: 'Tiến độ', exact: true }).click()
  await expect(page.getByText('Cancelled & rescheduled')).toBeVisible()
  await expect(page.getByText(/Unexpected work.*rescheduled automatically/)).toBeVisible()
})

test('uploads a Markdown file and shows an actionable backend-unavailable error', async ({ page }) => {
  await page.goto('/')
  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create study plan' })
  await dialog.getByLabel('Subject').first().fill('Biology')

  await dialog.getByLabel('Upload a document or recording').first().setInputFiles({
    name: 'biology.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Cell cycle\n## Mitosis\n## Membrane transport'),
  })
  await dialog.getByRole('button', { name: 'Analyze file' }).click()
  await expect(dialog.getByText(/topics extracted from biology.md/i)).toBeVisible()

  await page.route('**/api/analyze', async (route) => {
    await route.fulfill({ status: 500, contentType: 'text/plain', body: 'Internal Server Error' })
  })
  await dialog.getByLabel('Or paste a syllabus, notes, or topic outline').fill('Foundation')
  await dialog.getByRole('button', { name: 'Analyze pasted text' }).click()
  await expect(dialog.getByText(/Cannot reach the StudyGrid API/i)).toBeVisible()
})

test('passes automated WCAG A and AA checks for planner and setup', async ({ page }) => {
  await page.goto('/')

  const plannerResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  expect(summarizeViolations(plannerResults.violations)).toEqual([])

  await page.locator('.empty-calendar-overlay').getByRole('button', { name: 'Create study plan' }).click()
  const setupResults = await new AxeBuilder({ page })
    .include('.planner-dialog')
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  expect(summarizeViolations(setupResults.violations)).toEqual([])
})
