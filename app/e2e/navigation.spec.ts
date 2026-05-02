import { test, expect } from './fixtures';

test.describe('Tab Navigation', () => {
  test('app loads and shows explore tab by default', async ({ mockedPage: page }) => {
    await page.goto('/');
    await expect(page.getByRole('textbox', { name: 'Punto de partida' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Destino' })).toBeVisible();
  });

  test('can navigate to all four tabs', async ({ mockedPage: page }) => {
    await page.goto('/');

    // Explore tab (default)
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();

    // Record tab
    await page.getByRole('tab', { name: /Trazar/ }).click();
    await expect(page.getByTestId('record-swipe-switch')).toBeVisible();

    // Contribute tab
    await page.getByRole('tab', { name: /Contribuir/ }).click();
    await expect(page.getByRole('heading', { name: 'Contribuir' })).toBeVisible();

    // Favorites tab
    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByRole('heading', { name: 'Favoritos' })).toBeVisible();
  });
});
