/**
 * E2E test for the ramal descriptor flow (gap #7).
 *
 * After section voting on a multi-ramal line, the user is shown the
 * descriptor screen scoped to the route they just voted on, with:
 * - Existing descriptors listed by votes desc, with upvote chips.
 * - A "Ninguna describe esta línea" button that reveals a TextInput.
 * - "Listo" + "Saltar" exits.
 *
 * This spec walks the flow end-to-end against in-memory mocks:
 * 1. Open the section voting modal for line 205.
 * 2. Vote on every section.
 * 3. Verify the descriptor screen appears, with header showing
 *    `Beijing → Sacaba` and street summary (no `ramal_label`).
 * 4. Upvote an existing descriptor.
 * 5. Tap "Ninguna describe esta línea" → type → submit → see new row.
 * 6. Exit with "Listo" → see the "Votación completa" summary.
 */
import { test, expect } from './fixtures';
import { DESCRIPTORS_STORE } from './mocks';

const ROUTE_ID = 'route-205-1';

test.describe('Ramal descriptors after section voting', () => {
  test.beforeEach(async ({ mockedPage: page }) => {
    // Reset the descriptor store so tests don't pollute each other.
    DESCRIPTORS_STORE[ROUTE_ID] = [
      {
        id: 'desc-1', route_id: ROUTE_ID,
        text: 'lleva banderines naranjas en frente',
        votes_count: 5, created_at: '2026-04-30T10:00:00Z',
        voted_by_me: false,
      },
      {
        id: 'desc-2', route_id: ROUTE_ID,
        text: 'letrero con logo de Univalle',
        votes_count: 2, created_at: '2026-05-01T10:00:00Z',
        voted_by_me: false,
      },
    ];

    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
    await page.getByRole('tab', { name: /Contribuir/ }).click();
    await expect(
      page.getByRole('heading', { name: 'Contribuir' }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('shows the descriptor screen after voting on a multi-ramal line', async ({
    mockedPage: page,
  }) => {
    // Open section voting for line 205 (the multi-ramal line in mocks).
    await expect(page.getByText('Votar por secciones').first()).toBeVisible({
      timeout: 15000,
    });
    await page.getByText('Votar por secciones').first().click();

    // Vote 'approve' on each section.
    for (let i = 0; i < 2; i++) {
      const approve = page.getByText('Aprobar', { exact: true });
      await expect(approve).toBeVisible({ timeout: 10000 });
      await approve.click();
    }

    // Descriptor screen header — endpoint zones rendered, ramal_label NOT.
    await expect(page.getByText('Describí esta micro')).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByText('Beijing → Sacaba').first()).toBeVisible();
    await expect(page.getByText(/Av\. Beijing.*Av\. América/)).toBeVisible();
    // Decision #5 — internal labels never appear in the UI.
    await expect(page.getByText(/^main$|^r2$|ramal_label/)).not.toBeVisible();

    // Existing descriptors are listed in vote order (5 votes first).
    const banderines = page.getByText('lleva banderines naranjas en frente');
    const univalle = page.getByText('letrero con logo de Univalle');
    await expect(banderines).toBeVisible();
    await expect(univalle).toBeVisible();
  });

  test('upvotes an existing descriptor', async ({ mockedPage: page }) => {
    await page.getByText('Votar por secciones').first().click();
    for (let i = 0; i < 2; i++) {
      await page.getByText('Aprobar', { exact: true }).click();
    }
    await expect(page.getByText('Describí esta micro')).toBeVisible();

    const row = page.getByText('lleva banderines naranjas en frente');
    await expect(row).toBeVisible();
    // Vote count starts at 5 in the seeded store.
    await expect(page.getByText('5', { exact: true })).toBeVisible();

    await row.click();
    // After the upvote round-trip, count should bump to 6.
    await expect(page.getByText('6', { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test('creates a new descriptor via the "ninguna describe" path', async ({
    mockedPage: page,
  }) => {
    await page.getByText('Votar por secciones').first().click();
    for (let i = 0; i < 2; i++) {
      await page.getByText('Aprobar', { exact: true }).click();
    }
    await expect(page.getByText('Describí esta micro')).toBeVisible();

    // The TextInput shouldn't be visible until the user explicitly
    // confirms no existing descriptor matches.
    await expect(
      page.getByPlaceholder('Ej: lleva banderines naranjas en frente'),
    ).not.toBeVisible();

    await page.getByText('Ninguna describe esta línea').click();

    const input = page.getByPlaceholder(
      'Ej: lleva banderines naranjas en frente',
    );
    await expect(input).toBeVisible();
    await input.fill('asientos azules y música cumbia');
    await page.getByText('Enviar', { exact: true }).click();

    // The new descriptor appears in the list.
    await expect(page.getByText('asientos azules y música cumbia')).toBeVisible(
      { timeout: 5000 },
    );
  });

  test('"Listo" advances to the votación completa summary', async ({
    mockedPage: page,
  }) => {
    await page.getByText('Votar por secciones').first().click();
    for (let i = 0; i < 2; i++) {
      await page.getByText('Aprobar', { exact: true }).click();
    }
    await expect(page.getByText('Describí esta micro')).toBeVisible();
    await page.getByText('Listo', { exact: true }).click();

    await expect(page.getByText('Votación completa')).toBeVisible({
      timeout: 5000,
    });
  });
});
