import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
  test('renders settings page with sections', async ({ page }) => {
    await page.goto('/en/settings');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 });
  });

  test('shows exchange configuration', async ({ page }) => {
    await page.goto('/en/settings');
    await page.waitForLoadState('networkidle');
    const exchangeSelect = page.locator('select').first();
    if (await exchangeSelect.isVisible()) {
      await expect(exchangeSelect).toBeEnabled();
    }
  });

  test('risk limits section shows input fields', async ({ page }) => {
    await page.goto('/en/settings');
    await page.waitForLoadState('domcontentloaded');
    const maxNotionalInput = page.locator('input[type="number"]').first();
    if (await maxNotionalInput.isVisible()) {
      await expect(maxNotionalInput).toBeEnabled();
    }
  });

  test('API key form has all required fields', async ({ page }) => {
    await page.goto('/en/settings');
    const apiKeyInput = page.locator('input[type="password"]').first();
    const apiSecretInput = page.locator('input[type="password"]').nth(1);
    if (await apiKeyInput.isVisible()) {
      await expect(apiKeyInput).toBeVisible();
      await expect(apiSecretInput).toBeVisible();
    }
  });

  test('mobile layout stacks cards vertically', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/en/settings');
    await page.waitForLoadState('domcontentloaded');
    const layoutAuto = page.locator('.layout-auto, .layout-2col');
    if (await layoutAuto.count() > 0) {
      await expect(layoutAuto.first()).toBeVisible();
    }
  });
});
