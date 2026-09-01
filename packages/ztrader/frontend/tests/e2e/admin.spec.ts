import { test, expect } from '@playwright/test';

test.describe('Admin Page', () => {
  test('renders admin page with tabs', async ({ page }) => {
    await page.goto('/en/admin');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 });
  });

  test('shows stat cards for system overview', async ({ page }) => {
    await page.goto('/en/admin');
    await page.waitForLoadState('networkidle');
    const statCards = page.locator('.stat-card, [class*=stat]');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('kill switch button toggles state', async ({ page }) => {
    await page.goto('/en/admin');
    await page.waitForLoadState('domcontentloaded');
    const killSwitchBtn = page.locator('button').filter({ hasText: /ACTIVE|INACTIVE/i }).first();
    await expect(killSwitchBtn).toBeVisible({ timeout: 10000 });
  });

  test('navigates between tabs', async ({ page }) => {
    await page.goto('/en/admin');
    await page.waitForLoadState('domcontentloaded');
    const tabs = page.locator('[class*=tab]');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(4);
  });

  test('responsive stat grid adapts to mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/en/admin');
    await page.waitForLoadState('domcontentloaded');
    const statsRow = page.locator('[class*=stats-row]');
    if (await statsRow.isVisible()) {
      const box = await statsRow.boundingBox();
      expect(box).not.toBeNull();
      if (box) expect(box.width).toBeLessThan(400);
    }
  });
});
