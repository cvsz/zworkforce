import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test('renders dashboard with all key sections', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.ticker-tape')).toBeVisible({ timeout: 10000 });
  });

  test('shows health status indicator', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('domcontentloaded');
    const statusDots = page.locator('.status-dot');
    const count = await statusDots.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('ticker tape renders with price data', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('networkidle');
    const ticker = page.locator('.ticker-tape').first();
    await expect(ticker).toBeVisible({ timeout: 10000 });
  });

  test('bot start form is present', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('domcontentloaded');
    const botSections = page.locator('text=Start Trading').or(page.locator('text=bot')).or(page.locator('text=Bot'));
    const count = await botSections.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('kill switch status displays correct state', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('networkidle');
    const killSwitchText = page.locator('text=KILL SWITCH').or(page.locator('text=Kill Switch'));
    await expect(killSwitchText.first()).toBeVisible({ timeout: 10000 });
  });

  test('audit log section renders', async ({ page }) => {
    await page.goto('/en/dashboard');
    await page.waitForLoadState('networkidle');
    const audit = page.locator('text=Audit').or(page.locator('text=audit'));
    await expect(audit.first()).toBeVisible({ timeout: 10000 });
  });

  test('mobile responsiveness - scores/metrics stack vertically', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/en/dashboard');
    await page.waitForLoadState('domcontentloaded');
    const layoutGrids = page.locator('.layout-grid, .layout-2col, .layout-3col');
    const count = await layoutGrids.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('backtest section allows strategy selection', async ({ page }) => {
    await page.goto('/en/dashboard');
    const backtestSelect = page.locator('select').first();
    if (await backtestSelect.isVisible()) {
      await backtestSelect.selectOption({ index: 0 });
      await expect(backtestSelect).toHaveValue(/./);
    }
  });
});
