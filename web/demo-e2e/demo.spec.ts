import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { PublishedRun } from '../src/evaluation/evidence';

const published: { runs: PublishedRun[] } = JSON.parse(
  readFileSync(new URL('../src/generated/evidence.json', import.meta.url), 'utf8'),
);

test('public demo reviews, proofs and evidence work without sign-in or API requests', async ({
  page,
}) => {
  const apiRequests: string[] = [];
  const errors: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/**', (route) => route.abort());
  await page.goto('/');
  await expect(page).toHaveURL(/\/sample\/overview$/);
  await expect(page.locator('.balance-value')).toHaveText('R 39 280,00');
  await expect(page.getByRole('link', { name: 'Connected workspace' })).toHaveCount(0);
  await page.goto('/sample/review/sample-split?tab=evidence');
  await expect(page.getByText('The evidence behind the proposal')).toBeVisible();
  await page.reload();
  await expect(page.getByText('The evidence behind the proposal')).toBeVisible();
  await page.getByRole('tab', { name: 'Overview' }).click();
  await page.getByRole('button', { name: /Approve proposal/ }).click();
  await expect(page.getByRole('status')).toContainText('approved');
  await page.getByRole('link', { name: 'Activity', exact: true }).click();
  await expect(page.locator('.activity-item').first()).toContainText('Proposal approved');
  await page.getByRole('link', { name: 'Payment proofs', exact: true }).click();
  await page.getByRole('radio', { name: /A convincing document/ }).check();
  await page.getByRole('button', { name: 'Check sample claim' }).click();
  await expect(page.locator('.verdict-heading h2')).toHaveText('not received');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('link', { name: /Open connected/ })).toHaveCount(0);
  await page.getByRole('link', { name: 'Data imports' }).click();
  await expect(page.getByRole('link', { name: /Run the complete workspace/ })).toBeVisible();
  await expect(page.locator('input[type=file]')).toHaveCount(0);
  await page.goto('/sample/evaluation');
  await expect(page.getByRole('heading', { name: 'Evidence, in the open.' })).toBeVisible();
  await expect(page.locator('.gate-list li').first()).toBeVisible();
  for (const run of published.runs.filter((run) => run.provider !== 'stub' && run.report)) {
    await page.goto(
      `/sample/evaluation?provider=${run.provider}&retrieval=${run.retrieval_enabled ? 'on' : 'off'}`,
    );
    await expect(page.getByLabel('Inspect provider')).toHaveValue(run.provider);
    await expect(page.locator('.evaluation-detail-grid .status-badge')).toHaveText(
      run.report!.passed ? 'Gates passed' : 'Gates failed',
    );
    await expect(page.locator('.provenance .mono').first()).toHaveText(run.report_sha256!);
  }
  expect(apiRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test('public deep links, legacy URLs and phone navigation stay inside the demo', async ({
  page,
}) => {
  await page.goto('/workspace/review/sample-split?tab=audit');
  await expect(page).toHaveURL(/\/sample\/review\/sample-split\?tab=audit$/);
  await expect(page.getByText('Every decision, recorded.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Every decision, recorded.')).toBeVisible();
  await page.goto('/proofs');
  await expect(page).toHaveURL(/\/sample\/proofs$/);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['overview', 'review/sample-split', 'proofs', 'activity', 'settings']) {
    await page.goto(`/sample/${path}`);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('a[href^="/workspace"]')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});
