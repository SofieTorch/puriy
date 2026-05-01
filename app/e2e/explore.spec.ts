import { test, expect } from './fixtures';

test.describe('Explore Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
  });

  test('shows origin as "Ubicación actual" by default', async ({ page }) => {
    const origin = page.getByRole('textbox', { name: 'Punto de partida' });
    await expect(origin).toHaveValue('Ubicación actual');
  });

  test('can type in the destination field', async ({ page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza Colón');
    await expect(destInput).toHaveValue('Plaza Colón');
  });

  test('nearby lines section is visible', async ({ page }) => {
    // There are two elements with this testID; pick the visible one
    await expect(page.getByTestId('explore-nearby-title').last()).toBeVisible();
  });
});
