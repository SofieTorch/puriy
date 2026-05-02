import { test, expect } from './fixtures';

test.describe('Contribute Tab', () => {
  test.beforeEach(async ({ mockedPage: page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
    await page.getByRole('tab', { name: /Contribuir/ }).click();
    await expect(page.getByRole('heading', { name: 'Contribuir' })).toBeVisible({ timeout: 10000 });
  });

  test('shows pending routes from mock API', async ({ mockedPage: page }) => {
    await expect(page.getByTestId('contribute-routes-title')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Línea 205').last()).toBeVisible();
  });

  test('shows line familiarity voting section', async ({ mockedPage: page }) => {
    await expect(page.getByTestId('contribute-lines-title')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('contribute-line-approve-0')).toBeVisible();
    await expect(page.getByTestId('contribute-line-reject-0')).toBeVisible();
  });

  test('shows route cards with "Votar por secciones" action', async ({ mockedPage: page }) => {
    await expect(page.getByText('Votar por secciones')).toBeVisible({ timeout: 15000 });
  });

  test('can approve a line', async ({ mockedPage: page }) => {
    await expect(page.getByTestId('contribute-line-approve-0')).toBeVisible({ timeout: 15000 });
    await page.getByTestId('contribute-line-approve-0').click();
    await page.waitForTimeout(1000);
  });
});
