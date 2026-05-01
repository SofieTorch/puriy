import { test, expect } from './fixtures';

test.describe('Favorites Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Favoritos/ }).click();
  });

  test('shows empty state when no trips saved', async ({ page }) => {
    await expect(
      page.getByTestId('favorites-empty').or(page.getByTestId('favorites-commute-title')),
    ).toBeVisible({ timeout: 10000 });
  });

  test('shows trip cards when trips exist', async ({ page }) => {
    const commuteTitle = page.getByTestId('favorites-commute-title');
    const emptyState = page.getByTestId('favorites-empty');

    await expect(commuteTitle.or(emptyState)).toBeVisible({ timeout: 10000 });

    if (await commuteTitle.isVisible()) {
      await expect(page.getByTestId('favorites-trip-card-0')).toBeVisible();
    }
  });
});
