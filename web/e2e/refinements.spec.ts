import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { templates } from '../src/imports/templates';
import type { PublishedRun } from '../src/evaluation/evidence';

const published: { runs: PublishedRun[] } = JSON.parse(
  readFileSync(new URL('../src/generated/evidence.json', import.meta.url), 'utf8'),
);

const api = process.env.CLEARLINE_API_URL ?? 'http://127.0.0.1:18000';

test('published evidence and import templates remain available with the API blocked', async ({
  page,
}) => {
  const network: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) network.push(request.url());
  });
  await page.route('**/api/**', (route) => route.abort());
  await page.goto('/sample/overview');
  await page.getByRole('link', { name: /Inspect the evidence/ }).click();
  await expect(page).toHaveURL(/\/sample\/evaluation$/);
  await expect(page.getByRole('heading', { name: 'Evidence, in the open.' })).toBeVisible();
  const report = published.runs.find(
    (run) => run.provider === 'stub' && run.retrieval_enabled,
  )!.report!;
  await expect(page.locator('.evaluation-population > div').first()).toContainText(
    String(report.counts.bank_cases),
  );
  await expect(page.locator('.gate-list li')).toHaveCount(Object.keys(report.gates).length);
  await page.getByRole('link', { name: 'Retrieval off', exact: true }).click();
  await expect(page).toHaveURL(/retrieval=off/);
  await page.reload();
  await expect(page.getByRole('link', { name: 'Retrieval off', exact: true })).toHaveAttribute(
    'aria-current',
    'true',
  );
  const missing = published.runs.find(
    (run) => !run.retrieval_enabled && !run.report && run.provider !== 'stub',
  );
  if (missing) {
    await page.getByLabel('Inspect provider').selectOption(missing.provider);
    await expect(page.locator('.unmeasured-report')).toContainText('Not yet run.');
    await expect(page.locator('.evaluation-population')).toHaveCount(0);
    await page.goBack();
    await expect(page.getByLabel('Inspect provider')).toHaveValue('stub');
  }
  await page.screenshot({ path: '../docs/images/evaluation-evidence.png', fullPage: true });
  await page.goto('/sample/import');
  await expect(page.locator('input[type=file]')).toHaveCount(0);
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: /Download invoice template/ }).click();
  expect((await download).suggestedFilename()).toBe('clearline-invoices-template.csv');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['import', 'evaluation']) {
    await page.goto(`/sample/${route}`);
    await expect(page.locator('h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
  await page.screenshot({ path: '../docs/images/evaluation-phone.png', fullPage: true });
  expect(network).toEqual([]);
});

test('connected CSV previews are write-free, imports are explicit and duplicate records are skipped', async ({
  page,
  request,
}) => {
  await page.goto('/workspace/import');
  const before = await (await request.get(`${api}/metrics`)).json();
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({
    name: 'bad.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(templates.invoices.csv.replace('125000', 'invalid-cents')),
  });
  await page.getByRole('button', { name: 'Validate and preview' }).click();
  await expect(page.locator('.import-errors')).toContainText('Row 2');
  await expect(page.getByRole('button', { name: 'Import records', exact: true })).toHaveCount(0);
  for (const kind of ['invoices', 'bank-lines'] as const) {
    if (kind === 'bank-lines')
      await page.getByRole('radio', { name: 'Bank observations', exact: true }).check();
    for (let attempt = 0; attempt < 2; attempt++) {
      await page.getByLabel('CSV file', { exact: true }).setInputFiles({
        name: `${kind}.csv`,
        mimeType: 'text/csv',
        buffer: Buffer.from(templates[kind].csv),
      });
      await page.getByRole('button', { name: 'Validate and preview' }).click();
      await expect(page.getByText('Format validated', { exact: true })).toBeVisible();
      const submit = page.getByRole('button', { name: 'Import records', exact: true });
      await expect(submit).toBeDisabled();
      if (kind === 'invoices' && attempt === 0)
        expect((await (await request.get(`${api}/metrics`)).json()).bank_lines).toEqual(
          before.bank_lines,
        );
      await page.getByRole('checkbox', { name: /Import 1 validated record/ }).check();
      const response = page.waitForResponse(
        (response) => new URL(response.url()).pathname === `/api/ingest/${kind}`,
      );
      await submit.click();
      const actual = await (await response).json();
      expect(actual.inserted + actual.skipped).toBe(1);
      if (attempt === 1) expect(actual).toEqual({ inserted: 0, skipped: 1 });
      await expect(page.locator('.import-complete')).toContainText('Records, together.');
      await expect(page.locator('.import-complete')).toContainText(
        `${actual.inserted} imported · ${actual.skipped} already present`,
      );
    }
  }
  await page.screenshot({ path: '../docs/images/import-workspace.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('region', { name: 'CSV preview records' }).scrollIntoViewIfNeeded();
  await expect(page.getByRole('cell', { name: '2026-09-02', exact: true })).toBeInViewport();
  await page.screenshot({ path: '../docs/images/import-phone.png' });
  await page.getByRole('link', { name: 'Activity', exact: true }).click();
  await expect(page.locator('.activity-item').first()).toContainText('Bank lines imported');
});
