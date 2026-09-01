import { test, expect } from '@playwright/test';

test.describe('Login Page', () => {
  test('renders login page with title and Google sign-in button', async ({ page }) => {
    const response = await page.goto('/en/login');
    expect(response?.ok()).toBe(true);

    await expect(page.locator('h1')).toContainText('ztrader');
    await expect(page.locator('text=Sign in with Google').or(page.locator('[class*=google]'))).toBeVisible();
  });

  test('Google sign-in button is clickable', async ({ page }) => {
    await page.goto('/en/login');
    const button = page.locator('.glass-card-static button:has(svg)');
    await expect(button).toBeVisible();
    await expect(button).toBeEnabled();
  });

  test('shows connecting state when sign-in is clicked', async ({ page }) => {
    await page.goto('/en/login');
    await page.route('**/auth/google/authorize', async (route) => {
      await new Promise((r) => setTimeout(r, 3000));
      await route.fulfill({ status: 200, body: '{"authorization_url":"https://accounts.google.com/o/oauth2/auth?test"}' });
    });
    const button = page.locator('.glass-card-static button:has(svg)');
    await button.click();
    await expect(page.locator('text=Connecting...')).toBeVisible({ timeout: 2000 });
  });

  test('handles OAuth callback with token in URL', async ({ page }) => {
    await page.goto('/en/login?token=test-oauth-token-12345');
    await page.waitForFunction(() => localStorage.getItem('ztrader_admin_token') !== null, { timeout: 5000 });
    const token = await page.evaluate(() => localStorage.getItem('ztrader_admin_token'));
    expect(token).toBe('test-oauth-token-12345');
  });

  test('login page is responsive on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/en/login');
    const card = page.locator('.glass-card-static');
    const box = await card.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeLessThan(440);
      expect(box.height).toBeLessThan(600);
    }
    await expect(page.locator('h1')).toBeVisible();
  });
});
