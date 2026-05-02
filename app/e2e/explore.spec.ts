import { test, expect } from './fixtures';

test.describe('Explore Tab', () => {
  test.beforeEach(async ({ mockedPage: page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
  });

  test('shows origin as "Ubicación actual" by default', async ({ mockedPage: page }) => {
    const origin = page.getByRole('textbox', { name: 'Punto de partida' });
    await expect(origin).toHaveValue('Ubicación actual');
  });

  test('can type in the destination field', async ({ mockedPage: page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza Colón');
    await expect(destInput).toHaveValue('Plaza Colón');
  });

  test('shows nearby lines from mock API', async ({ mockedPage: page }) => {
    await expect(page.getByText('Línea 101').last()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Cala Cala - Zona Sur').last()).toBeVisible();
  });

  test('can search for directions and see results', async ({ mockedPage: page }) => {
    // Pick destination from autocomplete
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza');

    // Wait for autocomplete and click the suggestion
    const suggestion = page.getByText('Plaza Colón, Av. Ballivián', { exact: true });
    await expect(suggestion).toBeVisible({ timeout: 5000 });
    await suggestion.click();

    // Click the visible search button (there may be two in the DOM)
    await page.getByText('Buscar ruta').last().click();

    // Verify route results (mock: 630s ≈ 11min, 2600m = 2.6km)
    await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('2.6 km').first()).toBeVisible();
  });

  test('can view route detail after searching', async ({ mockedPage: page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza');

    const suggestion = page.getByText('Plaza Colón, Av. Ballivián', { exact: true });
    await expect(suggestion).toBeVisible({ timeout: 5000 });
    await suggestion.click();

    await page.getByText('Buscar ruta').last().click();
    await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });

    // Click route card to see detail
    await page.getByText('11 min').first().click();

    // Detail view shows step-by-step
    await expect(page.getByText('Caminar').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Tomar Línea 101')).toBeVisible();
    await expect(page.getByText('Llegaste')).toBeVisible();
  });
});
