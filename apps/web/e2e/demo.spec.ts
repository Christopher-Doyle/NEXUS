import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('approved demo completes with a report and persisted history', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Create task' }).click()
  await page.getByRole('button', { name: 'Create task' }).click()
  await page.getByRole('button', { name: 'Generate plan' }).click()
  await expect(page.getByRole('heading', { name: 'Review the steps.' })).toBeVisible()
  const planA11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  expect(planA11y.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, html: node.html })) }))).toEqual([])
  await page.getByRole('button', { name: 'Start approved plan' }).click()
  await expect(page.getByRole('heading', { name: 'Approval required' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve write' }).click()
  await expect(page.locator('.cockpit-head .chip')).toHaveText('completed')
  await expect(page.getByRole('heading', { name: 'Tool receipts' })).toBeVisible()
  await expect(page.getByText('Step 1: read_file v1 · attempt 1 · completed')).toBeVisible()
  const reportLink = page.getByRole('link', { name: 'project-report.md' })
  await expect(reportLink).toBeVisible()
  const reportUrl = await reportLink.getAttribute('href')
  expect(reportUrl).toBeTruthy()
  const report = await page.request.get(new URL(reportUrl!, page.url()).toString())
  expect(report.ok()).toBeTruthy()
  expect(await report.text()).toContain('## Citations')
  const cockpitA11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  expect(cockpitA11y.violations.map(item => item.id)).toEqual([])
  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByRole('link', { name: 'Read the sample project notes and generate a structured report.' })).toBeVisible()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export history for Read the sample project notes and generate a structured report.' }).click(),
  ])
  const exported = JSON.parse(await (await import('node:fs/promises')).readFile(await download.path(), 'utf-8'))
  expect(exported.format).toBe('nexus-task-history-v1')
  expect(exported.task.state).toBe('completed')
  expect(exported.journal.length).toBeGreaterThan(0)
  expect(exported.executions.some((item: { tool_name: string }) => item.tool_name === 'write_report')).toBeTruthy()
  expect(exported.artifacts.some((item: { filename: string }) => item.filename === 'project-report.md')).toBeTruthy()
})

test('rejected report write produces no artifact', async ({ page }) => {
  await page.goto('/tasks/new')
  await page.getByLabel('Goal').fill('Reject the sample project report safely.')
  await page.getByRole('button', { name: 'Create task' }).click()
  await page.getByRole('button', { name: 'Generate plan' }).click()
  await page.getByRole('button', { name: 'Start approved plan' }).click()
  await expect(page.getByRole('heading', { name: 'Approval required' })).toBeVisible()
  await page.getByRole('button', { name: 'Reject' }).click()
  await expect(page.locator('.cockpit-head .chip')).toHaveText('failed')
  await expect(page.getByText('No report has been written yet.')).toBeVisible()
})

test('mobile settings remain usable and persist a deadline', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link', { name: 'Settings' }).click()
  await expect(page.getByRole('heading', { name: 'Settings.' })).toBeVisible()
  const deadline = page.getByLabel('Task dispatch deadline, seconds')
  await deadline.fill('1200')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByRole('status')).toHaveText('Settings saved locally.')
  await page.reload()
  await expect(deadline).toHaveValue('1200')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
})

test('task form is operable in keyboard focus order', async ({ page }) => {
  await page.goto('/tasks/new')
  await page.getByLabel('Goal').focus()
  for (const label of ['Constraints', 'Success criteria', 'Approved workspace folder', 'Supporting files']) {
    await page.keyboard.press('Tab')
    await expect(page.getByLabel(label, { exact: false })).toBeFocused()
  }
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Create task' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Review the steps.' })).toBeVisible()
})

test('installed local Ollama model runs a reviewed plan', async ({ page }) => {
  test.skip(!process.env.NEXUS_E2E_OLLAMA_MODEL, 'Opt in with an already installed local model')
  test.setTimeout(180_000)
  await page.goto('/tasks/new')
  await page.getByRole('button', { name: 'Create task' }).click()
  await page.getByLabel('Planning mode').selectOption('ollama')
  await page.getByRole('button', { name: 'Generate plan' }).click()
  await expect(page.getByRole('status')).toHaveText('Plan generated.', { timeout: 170_000 })
  await expect(page.getByRole('button', { name: 'Start approved plan' })).toBeEnabled()
  expect(await page.locator('.step-card').count()).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Start approved plan' }).click()
  const approval = page.getByRole('heading', { name: 'Approval required' })
  await expect(approval.or(page.locator('.cockpit-head .chip').filter({ hasText: 'completed' }))).toBeVisible({ timeout: 60_000 })
  if (await approval.isVisible()) await page.getByRole('button', { name: 'Approve write' }).click()
  await expect(page.locator('.cockpit-head .chip')).toHaveText('completed', { timeout: 60_000 })
})

for (const path of ['/', '/tasks/new', '/settings']) {
  test(`core page ${path} has no automated WCAG A or AA findings`, async ({ page }) => {
    await page.goto(path)
    if (path === '/settings') await expect(page.getByRole('button', { name: 'Save settings' })).toBeVisible()
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    expect(results.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }))).toEqual([])
  })
}
