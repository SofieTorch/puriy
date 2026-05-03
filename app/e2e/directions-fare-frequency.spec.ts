/**
 * E2E coverage for RF-03 (tarifa estimada), RF-04 (frecuencia) and
 * RF-30 (tarifa total) — verifies the badges show up in the route
 * results card and in the per-leg detail view.
 *
 * The mocked /directions/ response in `mocks.ts` carries:
 *   - bus leg with fare_bob = 2.5, frequency_min = 8
 *   - total_fare_bob = 2.5
 */
import { test, expect } from './fixtures';

test.describe('Tarifa y frecuencia en planificación', () => {
  test.beforeEach(async ({ mockedPage: page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
  });

  test('result card shows total fare and per-line frequency', async ({ mockedPage: page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza');
    const suggestion = page.getByText('Plaza Colón, Av. Ballivián', { exact: true });
    await expect(suggestion).toBeVisible({ timeout: 5000 });
    await suggestion.click();
    await page.getByText('Buscar ruta').last().click();

    // Wait for results to render.
    await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });

    // RF-30: total fare badge is visible on the route card.
    await expect(page.getByTestId('route-0-total-fare')).toBeVisible();
    await expect(page.getByTestId('route-0-total-fare')).toHaveText('Bs. 2.50');

    // RF-04: frequency text appears next to the bus chip.
    await expect(page.getByText('c/ 8 min').first()).toBeVisible();
  });

  test('detail view shows fare and frequency for each bus leg', async ({ mockedPage: page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza');
    const suggestion = page.getByText('Plaza Colón, Av. Ballivián', { exact: true });
    await expect(suggestion).toBeVisible({ timeout: 5000 });
    await suggestion.click();
    await page.getByText('Buscar ruta').last().click();
    await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });

    // Open the route detail.
    await page.getByText('11 min').first().click();
    await expect(page.getByText('Tomar Línea 101')).toBeVisible({ timeout: 5000 });

    // The bus leg in the mock is at index 1 (walk · bus · walk).
    const meta = page.getByTestId('leg-1-meta');
    await expect(meta).toBeVisible();
    await expect(meta).toContainText('Bs. 2.50');
    await expect(meta).toContainText('c/ 8 min');
  });

  test('walk legs do not show fare/frequency', async ({ mockedPage: page }) => {
    const destInput = page.getByRole('textbox', { name: 'Destino' });
    await destInput.fill('Plaza');
    await page.getByText('Plaza Colón, Av. Ballivián', { exact: true }).click();
    await page.getByText('Buscar ruta').last().click();
    await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });
    await page.getByText('11 min').first().click();
    await expect(page.getByText('Caminar').first()).toBeVisible({ timeout: 5000 });

    // Walk legs (indices 0 and 2 in the mock) shouldn't have a meta line.
    await expect(page.getByTestId('leg-0-meta')).toHaveCount(0);
    await expect(page.getByTestId('leg-2-meta')).toHaveCount(0);
  });
});
