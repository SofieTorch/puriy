import { test, expect } from './fixtures';

test.describe('Favorites Tab', () => {
  test('shows empty state when no trips saved', async ({ mockedPage: page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByTestId('favorites-empty')).toBeVisible({ timeout: 10000 });
  });

  test('can navigate to favorites and back', async ({ mockedPage: page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByRole('heading', { name: 'Favoritos' })).toBeVisible();

    // Go back to explore
    await page.getByRole('tab', { name: /Explorar/ }).click();
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
  });
});
