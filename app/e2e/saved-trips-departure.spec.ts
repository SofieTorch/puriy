/**
 * E2E coverage for CU-04 (departureTime in saved trips) and the
 * client-side parts of CU-14 (notification scheduling).
 *
 * The actual delivery of OS notifications is verified manually in the
 * smoke checklist (TC-14 / TC-15) — Playwright web cannot trigger
 * native scheduling. What Playwright DOES verify here:
 *  - the new Save Trip modal accepts time input and validates HH:mm,
 *  - saving a trip with a time persists `departureTime` and surfaces
 *    a departure badge on the favorites card,
 *  - saving without a time hides the badge,
 *  - total fare from #2 is rendered on favorites cards.
 *
 * Note on alerts: `Alert.alert` on react-native-web is a synchronous
 * `window.alert()` — Playwright auto-dismisses it and it isn't part
 * of the DOM, so we intercept the dialog event instead of asserting
 * on its body text.
 */
import { test, expect, Page } from '@playwright/test';
import { test as base } from './fixtures';

// Auto-dismiss any window.alert that fires (saveTrip confirmation).
const tWithDialog = base.extend<{ mockedPage: Page }>({
  mockedPage: async ({ mockedPage }, use) => {
    mockedPage.on('dialog', (d) => d.dismiss().catch(() => undefined));
    await use(mockedPage);
  },
});

async function planAndOpenSaveModal(page: Page) {
  const destInput = page.getByRole('textbox', { name: 'Destino' });
  await destInput.fill('Plaza');
  const suggestion = page.getByText('Plaza Colón, Av. Ballivián', { exact: true });
  await expect(suggestion).toBeVisible({ timeout: 5000 });
  await suggestion.click();
  await page.getByText('Buscar ruta').last().click();
  await expect(page.getByText('11 min').first()).toBeVisible({ timeout: 10000 });
  await page.getByText('11 min').first().click();
  await expect(page.getByText('Tomar Línea 101')).toBeVisible({ timeout: 5000 });
  await page.getByTestId('explore-save-btn').click();
  await expect(page.getByText('Guardar ruta')).toBeVisible();
}

tWithDialog.describe('Save Trip Modal — hora de salida y notificaciones', () => {
  tWithDialog.beforeEach(async ({ mockedPage: page }) => {
    // Wipe OPFS so each test starts with an empty saved-trips table.
    // This is the only way to isolate tests since `expo-sqlite/web` uses
    // OPFS for persistence and Playwright's per-context storage state
    // doesn't reach inside the OPFS sandbox.
    await page.goto('/');
    await page.evaluate(async () => {
      try {
        const root = await (navigator.storage as { getDirectory(): Promise<FileSystemDirectoryHandle> }).getDirectory();
        for await (const [name] of (root as unknown as { entries(): AsyncIterable<[string, FileSystemHandle]> }).entries()) {
          await root.removeEntry(name, { recursive: true }).catch(() => undefined);
        }
      } catch {
        // ignore — OPFS may not be available in some browsers.
      }
    });
    // Reload so the DB re-initializes against an empty OPFS.
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
  });

  tWithDialog('modal lets the user pick type and an optional time', async ({ mockedPage: page }) => {
    await planAndOpenSaveModal(page);

    await page.getByTestId('save-trip-type-commute').click();
    await page.getByTestId('save-trip-time').fill('07:30');
    await page.getByTestId('save-trip-confirm').click();

    // Modal closes (input field gone).
    await expect(page.getByTestId('save-trip-time')).toHaveCount(0);

    // Verify the trip was persisted by checking the favorites card.
    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByTestId('favorites-departure-0')).toContainText('07:30');
  });

  tWithDialog('rejects malformed times', async ({ mockedPage: page }) => {
    await planAndOpenSaveModal(page);
    await page.getByTestId('save-trip-time').fill('25:99');
    await page.getByTestId('save-trip-confirm').click();
    await expect(page.getByTestId('save-trip-error')).toBeVisible();
    await expect(page.getByTestId('save-trip-error')).toContainText('HH:mm');
    // Modal stays open after a rejected save.
    await expect(page.getByTestId('save-trip-time')).toBeVisible();
  });

  tWithDialog('saved trip with time appears in favorites with departure badge and fare', async ({ mockedPage: page }) => {
    await planAndOpenSaveModal(page);
    await page.getByTestId('save-trip-type-commute').click();
    await page.getByTestId('save-trip-time').fill('07:30');
    await page.getByTestId('save-trip-confirm').click();

    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByRole('heading', { name: 'Favoritos' })).toBeVisible();

    // The mocked DirectionsResponse carries total_fare_bob = 2.5.
    await expect(page.getByTestId('favorites-fare-0')).toHaveText('Bs. 2.50');
    await expect(page.getByTestId('favorites-departure-0')).toContainText('07:30');
  });

  tWithDialog('saving without a time leaves departure badge hidden', async ({ mockedPage: page }) => {
    await planAndOpenSaveModal(page);
    // Don't fill time; confirm with default "Solo por hoy".
    await page.getByTestId('save-trip-confirm').click();
    await expect(page.getByTestId('save-trip-time')).toHaveCount(0);

    await page.getByRole('tab', { name: /Favoritos/ }).click();
    await expect(page.getByRole('heading', { name: 'Favoritos' })).toBeVisible();

    // Card visible but no departure badge.
    await expect(page.getByTestId('favorites-trip-card-0')).toBeVisible();
    await expect(page.getByTestId('favorites-departure-0')).toHaveCount(0);
  });
});

// Suppress the "test imports `expect` but doesn't use it" lint hint by
// referencing it once at the bottom — `expect` IS used inside the helpers.
void expect;
void test;
