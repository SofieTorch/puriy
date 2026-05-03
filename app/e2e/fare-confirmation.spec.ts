/**
 * E2E for CU-09 / RF-26 / RF-28 — fare confirmation chips.
 *
 * Verifies that after a line is selected in the SaveRecord modal:
 *  - the previously-reported amounts render as chips (mocked
 *    `common_amounts` from `/fares/lines/{id}`),
 *  - tapping a chip submits the fare with `source = "confirmation"`,
 *  - typing into the free input submits with `source = "registration"`.
 *
 * The transport-layer assertion uses `page.waitForRequest` to capture
 * the POST body of `/fares/reports`.
 */
import { test, expect, BUS_ROUTE_POINTS, simulateMovement } from './fixtures';

async function recordAndOpenSaveModal(
  page: import('@playwright/test').Page,
  context: import('@playwright/test').BrowserContext,
) {
  await page.goto('/');
  await page.getByRole('tab', { name: /Trazar/ }).click();
  await expect(page.getByTestId('record-swipe-switch')).toBeVisible();

  const switchEl = page.getByTestId('record-swipe-switch');
  const box = await switchEl.boundingBox();
  if (!box) throw new Error('Switch not found');
  await page.mouse.move(box.x + 36, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 36, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();

  await expect(page.getByTestId('record-duration')).toBeVisible({ timeout: 5000 });
  await simulateMovement(context, BUS_ROUTE_POINTS.slice(0, 3), 2000);

  const box2 = await switchEl.boundingBox();
  if (!box2) throw new Error('Switch not found');
  await page.mouse.move(box2.x + box2.width - 36, box2.y + box2.height / 2);
  await page.mouse.down();
  await page.mouse.move(box2.x + 36, box2.y + box2.height / 2, { steps: 10 });
  await page.mouse.up();

  await expect(page.getByTestId('modal-title')).toBeVisible({ timeout: 5000 });

  // Open the line dropdown and pick the first option (mocked as Line 101).
  await page.getByTestId('modal-line-dropdown').click();
  await page.getByTestId('modal-line-option-line-101').first().click();
}

test.describe('Fare confirmation chips', () => {
  test('renders chips from common_amounts', async ({ mockedPage: page, context }) => {
    await recordAndOpenSaveModal(page, context);
    await expect(page.getByTestId('modal-fare-chips')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('modal-fare-chip-2.50')).toBeVisible();
    await expect(page.getByTestId('modal-fare-chip-3.00')).toBeVisible();
  });

  test('tapping a chip submits source=confirmation', async ({ mockedPage: page, context }) => {
    await recordAndOpenSaveModal(page, context);
    await expect(page.getByTestId('modal-fare-chip-2.50')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('modal-fare-chip-2.50').click();

    // Confirm the chip's value populated the input.
    await expect(page.getByTestId('modal-fare-input')).toHaveValue('2.50');

    // Fire the save and capture the POST body.
    const reqPromise = page.waitForRequest((req) =>
      req.url().includes('/fares/reports') && req.method() === 'POST',
    );
    await page.getByTestId('modal-save-btn').click();
    const req = await reqPromise;
    const body = req.postDataJSON();
    expect(body.amount_bob).toBe(2.5);
    expect(body.source).toBe('confirmation');
  });

  test('typing in the input submits source=registration', async ({ mockedPage: page, context }) => {
    await recordAndOpenSaveModal(page, context);
    await expect(page.getByTestId('modal-fare-input')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('modal-fare-input').fill('5.50');

    const reqPromise = page.waitForRequest((req) =>
      req.url().includes('/fares/reports') && req.method() === 'POST',
    );
    await page.getByTestId('modal-save-btn').click();
    const req = await reqPromise;
    const body = req.postDataJSON();
    expect(body.amount_bob).toBe(5.5);
    expect(body.source).toBe('registration');
  });
});
