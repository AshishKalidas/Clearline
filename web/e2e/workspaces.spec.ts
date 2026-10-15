import { expect, test } from '@playwright/test';
import { money } from '../src/api';
import type { BankLine, Metrics } from '../src/types';

const api = process.env.CLEARLINE_API_URL ?? 'http://127.0.0.1:18000';

test('sample reviews and proofs work with every API request blocked', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) requests.push(request.url());
  });
  await page.route('**/api/**', (route) => route.abort());
  await page.goto('/');
  await expect(page).toHaveURL(/\/sample\/overview$/);
  await expect(page.locator('.balance-value')).toHaveText('R 39 280,00');
  await page.screenshot({ path: '../docs/images/workspace-overview.png', fullPage: true });
  await page.goto('/sample/review/sample-split');
  await expect(page.locator('.detail-heading')).toContainText('Aster Workshop');
  await page.getByRole('button', { name: /Approve proposal/ }).click();
  await expect(page.getByRole('status')).toContainText('approved');
  await page.getByRole('link', { name: 'Activity', exact: true }).click();
  await expect(page.locator('.activity-item').first()).toContainText('Proposal approved');
  await expect(page.locator('.activity-item').first()).toContainText('Aster Workshop');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Reset sample decisions' }).click();
  await page.getByRole('link', { name: 'Payment proofs', exact: true }).click();
  await page.getByRole('radio', { name: /A convincing document/ }).check();
  await page.getByRole('button', { name: 'Check sample claim' }).click();
  await expect(page.locator('.verdict-heading')).toContainText('Do not release goods');
  await expect(page.locator('.verdict-heading h2')).toHaveText('not received');
  expect(requests).toEqual([]);
});

test('deep links, query state, refresh and browser history stay on the chosen payment', async ({
  page,
}) => {
  await page.goto('/sample/review/sample-split?tab=evidence');
  await expect(page.getByText('The evidence behind the proposal')).toBeVisible();
  await page.getByRole('tab', { name: 'Audit trail' }).click();
  await expect(page).toHaveURL(/tab=audit/);
  await page.reload();
  await expect(page.getByText('Every decision, recorded.')).toBeVisible();
  await page.getByRole('tab', { name: 'Overview' }).click();
  await page.goBack();
  await expect(page.getByText('Every decision, recorded.')).toBeVisible();
  await page.goForward();
  await expect(page.locator('.bank-amount')).toHaveText('R 3 700,00');
  await page.getByLabel('Search payments').fill('Lumen');
  await expect(page).toHaveURL(/q=Lumen/);
  await page.reload();
  await expect(page.getByLabel('Search payments')).toHaveValue('Lumen');
  await expect(page.locator('.detail-heading')).toContainText('Aster Workshop');
  await page.goto('/sample/review/unknown-proposal');
  await expect(page.getByRole('heading', { name: 'Payment unavailable' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Approve proposal/ })).toHaveCount(0);
  await page.goto('/sample/not-a-route');
  await expect(page.getByRole('heading', { name: 'A small wrong turn.' })).toBeVisible();
  await page.getByRole('link', { name: /Back to overview/ }).click();
  await expect(page).toHaveURL(/\/sample\/overview$/);
});

test('appearance persists and mobile layouts keep navigation and amounts accessible', async ({
  page,
}) => {
  await page.goto('/sample/settings');
  await page.getByRole('radio', { name: 'Dark', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('radio', { name: 'Dark', exact: true })).toBeChecked();
  await page.goto('/sample/overview');
  await expect(page.locator('.balance-value')).toHaveText('R 39 280,00');
  await page.screenshot({ path: '../docs/images/workspace-dark.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['overview', 'review/sample-split', 'proofs', 'activity', 'settings']) {
    await page.goto(`/sample/${route}`);
    await expect(page.locator('h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await expect(page.getByRole('link', { name: 'Overview', exact: true })).toBeVisible();
  }
  await page.goto('/sample/overview');
  await page.screenshot({ path: '../docs/images/workspace-mobile.png', fullPage: true });
  const protocol = await page.context().newCDPSession(page);
  await protocol.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-transparency', value: 'reduce' }],
  });
  await expect(page.locator('.glass').first()).toHaveCSS('backdrop-filter', 'none');
  await protocol.send('Emulation.setEmulatedMedia', { features: [] });
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await expect(page.locator('.glass').first()).toHaveCSS('backdrop-filter', 'none');
  const button = page.getByRole('button', { name: 'Reset sample' });
  await button.focus();
  await expect(button).toHaveCSS('outline-width', '4px');
  expect(
    await button.evaluate((element) => parseFloat(getComputedStyle(element).transitionDuration)),
  ).toBeLessThan(0.001);
});

test('connected live panel uses API values, pauses polling and recovers from an outage', async ({
  page,
  request,
}) => {
  const metrics: Metrics = await (await request.get(`${api}/metrics`)).json();
  const bankLines: BankLine[] = await (await request.get(`${api}/bank-lines?limit=1000`)).json();
  let calls = 0;
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/metrics') calls++;
  });
  await page.goto('/workspace/overview');
  await expect(page.locator('.live-panel .status-badge')).toHaveText('Connected');
  const actualTotal = money(bankLines.reduce((sum, line) => sum + line.amount_cents, 0));
  await expect(page.locator('.balance-value')).toHaveText(actualTotal);
  await expect(page.locator('.summary-stats > div').first()).toContainText(
    String(metrics.bank_lines.matched),
  );
  await page.screenshot({ path: '../docs/images/workspace-connected.png', fullPage: true });
  await page.getByRole('button', { name: 'Pause live updates' }).click();
  const pausedCalls = calls;
  await page.waitForTimeout(10500);
  expect(calls).toBe(pausedCalls);
  await expect(page.locator('.live-panel .status-badge')).toHaveText('Paused');
  await page.getByRole('button', { name: 'Resume live updates' }).click();
  await expect.poll(() => calls).toBeGreaterThan(pausedCalls);
  await expect(page.locator('.live-panel .status-badge')).toHaveText('Connected');
  await page.route('**/api/healthz', (route) => route.abort());
  await page.getByRole('button', { name: 'Refresh live panel' }).click();
  await expect(page.getByRole('alert')).toContainText('Workspace connection unavailable');
  await expect(page.locator('.live-panel .status-badge')).toHaveText('Offline');
  await expect(page.locator('.balance-value')).toHaveText(actualTotal);
  await page.unroute('**/api/healthz');
  await page.getByRole('button', { name: 'Refresh live panel' }).click();
  await expect(page.locator('.live-panel .status-badge')).toHaveText('Connected');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('a pending review can finish without pulling the user away from another page', async ({
  page,
  request,
}) => {
  const proposals: import('../src/types').Proposal[] = await (
    await request.get(`${api}/proposals`)
  ).json();
  const proposal = proposals.find((item) => item.decision === 'match' && !item.risk_flags.length);
  expect(proposal).toBeTruthy();
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**/api/proposals/${proposal!.id}/approve`, async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto(`/workspace/review/${proposal!.id}`);
  await expect(page.getByRole('button', { name: /Approve proposal/ })).toBeVisible();
  await Promise.all([
    page.waitForRequest((request) => request.url().endsWith(`/proposals/${proposal!.id}/approve`)),
    page.getByRole('button', { name: /Approve proposal/ }).click(),
  ]);
  try {
    await page.getByRole('link', { name: 'Payment proofs', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Verify before you release.' })).toBeVisible();
    const response = page.waitForResponse((response) =>
      response.url().endsWith(`/proposals/${proposal!.id}/approve`),
    );
    const refreshed = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/metrics',
    );
    release();
    expect((await response).status()).toBe(200);
    await refreshed;
    await expect(page).toHaveURL(/\/workspace\/proofs$/);
    await expect(page.getByLabel('Proof of payment PDF')).toBeAttached();
  } finally {
    release();
  }
});
