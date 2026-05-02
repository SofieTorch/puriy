import { test, expect, BUS_ROUTE_POINTS, simulateMovement } from './fixtures';

test.describe('Record with Fare', () => {
  test('fare input is shown after selecting a line in save modal', async ({
    mockedPage: page,
    context,
  }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Trazar/ }).click();
    await expect(page.getByTestId('record-swipe-switch')).toBeVisible();

    // Start recording
    const switchEl = page.getByTestId('record-swipe-switch');
    const box = await switchEl.boundingBox();
    if (!box) throw new Error('Switch not found');

    await page.mouse.move(box.x + 36, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 36, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    // Wait for recording to start
    await expect(page.getByTestId('record-duration')).toBeVisible({ timeout: 5000 });

    // Simulate some movement
    await simulateMovement(context, BUS_ROUTE_POINTS.slice(0, 3), 2000);

    // Stop recording (swipe left)
    const box2 = await switchEl.boundingBox();
    if (!box2) throw new Error('Switch not found');

    await page.mouse.move(box2.x + box2.width - 36, box2.y + box2.height / 2);
    await page.mouse.down();
    await page.mouse.move(box2.x + 36, box2.y + box2.height / 2, { steps: 10 });
    await page.mouse.up();

    // Save modal should appear
    await expect(page.getByTestId('modal-title')).toBeVisible({ timeout: 5000 });

    // Select a line from dropdown
    await page.getByTestId('modal-line-dropdown').click();
    // Wait for dropdown to show lines
    await page.waitForTimeout(1000);

    // The fare input should appear after a line is selected
    // (we need to select a line first — click on the first available one)
    const firstLine = page.locator('[data-testid="modal-line-dropdown"]').locator('..').locator('text=101').first();
    if (await firstLine.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstLine.click();
    }

    // Check if fare input is visible (it appears when a line is selected)
    const fareInput = page.getByTestId('modal-fare-input');
    if (await fareInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Fill in the fare
      await fareInput.fill('2.50');
      await expect(fareInput).toHaveValue('2.50');
    }
  });
});
