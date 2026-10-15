import { expect, test } from '@playwright/test';
import type { Proposal } from '../src/types';

const api = process.env.CLEARLINE_API_URL ?? 'http://127.0.0.1:18000';
const headers = { 'X-API-Key': 'clearline-local-demo', 'X-Reviewer': 'Synthetic Browser Reviewer' };

test.beforeAll(async ({ request }) => {
  const metrics = await (await request.get(`${api}/metrics`)).json();
  expect(metrics.provider).toBe('stub');
  expect((await request.post(`${api}/runs/reconcile`, { headers })).ok()).toBeTruthy();
});

test('review evidence, approve, reject and correct real synthetic proposals', async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/workspace/review');
  await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible();
  await expect(page.locator('.bank-amount')).toContainText('R ');
  await page.screenshot({ path: '../docs/images/review-workspace.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy();
  await page.setViewportSize({ width: 1440, height: 1000 });

  let queue: Proposal[] = await (await request.get(`${api}/proposals`)).json();
  const match = queue.find((p) => p.decision === 'match');
  expect(match).toBeTruthy();
  await page.locator('.queue-item').filter({ hasText: match!.bank_line.payer_name }).click();
  await expect(page.locator('.detail-heading')).toContainText(match!.bank_line.payer_name);
  await page.getByRole('tab', { name: /Evidence/ }).click();
  await expect(page.getByText('The evidence behind the proposal')).toBeVisible();
  await page.screenshot({ path: '../docs/images/investigation-evidence.png', fullPage: true });
  await page.getByRole('tab', { name: 'Audit trail' }).click();
  await expect(page.getByText('Every decision, recorded.')).toBeVisible();
  await page.getByRole('tab', { name: 'Overview' }).click();
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes(`/proposals/${match!.id}/approve`) && r.status() === 200,
    ),
    page.keyboard.press('a'),
  ]);
  expect((await (await request.get(`${api}/proposals/${match!.id}`)).json()).status).toBe(
    'approved',
  );
  await expect(page.getByRole('status')).toContainText('approved');

  queue = await (await request.get(`${api}/proposals`)).json();
  const escalate = queue.find((p) => p.decision === 'escalate');
  expect(escalate).toBeTruthy();
  await page.locator('.queue-item').filter({ hasText: escalate!.bank_line.payer_name }).click();
  await expect(page.locator('.detail-heading')).toContainText(escalate!.bank_line.payer_name);
  await page.getByRole('button', { name: /^Reject/ }).click();
  await expect(page.getByRole('button', { name: 'Reject proposal' })).toBeDisabled();
  await page
    .getByLabel('Review note')
    .fill('Synthetic reviewer requires independent payer evidence.');
  await page.getByRole('button', { name: 'Reject proposal' }).click();
  await expect(page.getByRole('status')).toContainText('rejected');
  expect((await (await request.get(`${api}/proposals/${escalate!.id}`)).json()).status).toBe(
    'rejected',
  );

  queue = await (await request.get(`${api}/proposals`)).json();
  const split = queue.find((p) => p.decision === 'split');
  expect(split).toBeTruthy();
  await page.locator('.queue-item').filter({ hasText: split!.bank_line.payer_name }).click();
  await expect(page.locator('.detail-heading')).toContainText(split!.bank_line.payer_name);
  await page.getByRole('button', { name: 'Correct', exact: true }).click();
  await expect(page.getByLabel('Corrected invoice 1')).toBeVisible();
  await page.getByLabel('Corrected invoice 1').selectOption(split!.allocations[0].invoice_number);
  await page.getByLabel('Corrected amount 1').fill(String(split!.allocations[0].amount_cents));
  await page
    .getByLabel('Review note')
    .fill('Synthetic reviewer independently confirmed these invoice allocations.');
  await page.getByRole('button', { name: 'Save corrected resolution' }).click();
  await expect(page.getByRole('status')).toContainText('Corrected resolution saved');
  const corrected = await (await request.get(`${api}/proposals/${split!.id}`)).json();
  expect(corrected.status).toBe('rejected');
  expect(corrected.bank_line.status).toBe('matched');
  expect(
    corrected.trace.some(
      (event: { event_type: string; payload: { source?: string } }) =>
        event.event_type === 'resolution_applied' && event.payload.source === 'human',
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test('verify genuine and absent payment claims from the browser', async ({ page }) => {
  await page.goto('/workspace/review');
  await page.getByRole('link', { name: 'Payment proofs', exact: true }).click();
  await page
    .getByLabel('Proof of payment PDF')
    .setInputFiles('../evals/datasets/seed-42/pops/proof-001.pdf');
  await page.getByRole('button', { name: /Verify payment claim/ }).click();
  await expect(page.locator('.verdict-heading h2')).toHaveText('verified');
  await page.screenshot({ path: '../docs/images/proof-verification.png', fullPage: true });
  await page
    .getByLabel('Proof of payment PDF')
    .setInputFiles('../evals/datasets/seed-42/pops/proof-031.pdf');
  await page.getByRole('button', { name: /Verify payment claim/ }).click();
  await expect(page.locator('.verdict-heading h2')).toHaveText('not received');
  await expect(page.locator('.verdict-heading')).toContainText('Do not release goods');
});
