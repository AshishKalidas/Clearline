import { expect, test } from '@playwright/test';

test('production navigation blurs scrolling content in both appearances and at phone size', async ({
  page,
}) => {
  for (const theme of ['Light', 'Dark']) {
    await page.goto('/sample/settings');
    await page.getByRole('radio', { name: theme, exact: true }).check();
    await page.goto('/sample/review/sample-split');
    await expect(page.locator('.bank-amount')).toBeVisible();
    // Place actual page text behind the floating toolbar, beyond its initial position.
    await page.locator('.detail-heading h2').evaluate((element) => {
      scrollTo(0, element.getBoundingClientRect().top + scrollY - 44);
    });
    await expect(page.locator('.topbar')).toHaveCSS('backdrop-filter', 'saturate(1.8) blur(20px)');
    expect(
      await page.locator('.main-shell').evaluate((element) => {
        const edge = getComputedStyle(element, '::before');
        return { blur: edge.backdropFilter, interactive: edge.pointerEvents };
      }),
    ).toEqual({ blur: 'blur(12px)', interactive: 'none' });
    await expect(page.getByRole('link', { name: 'Sample workspace', exact: true })).toBeVisible();
    await page.screenshot({ path: `../docs/images/navigation-scroll-${theme.toLowerCase()}.png` });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => scrollTo(0, 800));
    await expect(page.locator('.sidebar')).toHaveCSS('backdrop-filter', 'saturate(1.8) blur(20px)');
    await expect(page.locator('.topbar')).toHaveCSS('backdrop-filter', 'saturate(1.8) blur(20px)');
    await page.screenshot({ path: `../docs/images/navigation-phone-${theme.toLowerCase()}.png` });
    // Decorations must never intercept navigation while the page is scrolled.
    await page.getByRole('link', { name: 'Proofs', exact: true }).click();
    await expect(page).toHaveURL(/\/sample\/proofs$/);
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  await page.emulateMedia({ contrast: 'more' });
  await expect(page.locator('.topbar')).toHaveCSS('backdrop-filter', 'none');
  expect(
    await page
      .locator('.main-shell')
      .evaluate((element) => getComputedStyle(element, '::before').maskImage),
  ).toBe('none');
});
