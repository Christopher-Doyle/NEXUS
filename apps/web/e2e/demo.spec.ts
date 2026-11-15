import { expect, test } from '@playwright/test'

test('approved demo completes with a report and persisted history', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Create task' }).click()
  await page.getByRole('button', { name: 'Create task' }).click()
  await page.getByRole('button', { name: 'Generate plan' }).click()
  await expect(page.getByRole('heading', { name: 'Review the steps.' })).toBeVisible()
  await page.getByRole('button', { name: 'Start approved plan' }).click()
  await expect(page.getByRole('heading', { name: 'Approval required' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve write' }).click()
  await expect(page.locator('.cockpit-head .chip')).toHaveText('completed')
  await expect(page.getByRole('link', { name: 'project-report.md' })).toBeVisible()
  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByRole('link', { name: 'Read the sample project notes and generate a structured report.' })).toBeVisible()
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
