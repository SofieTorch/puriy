import { test, expect, BUS_ROUTE_POINTS, simulateMovement } from './fixtures';

test.describe('Record Tab', () => {
  test.beforeEach(async ({ mockedPage: page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Trazar/ }).click();
    await expect(page.getByTestId('record-swipe-switch')).toBeVisible();
  });

  test('shows the swipe switch in off state', async ({ mockedPage: page }) => {
    await expect(page.getByTestId('record-swipe-switch')).toBeVisible();
  });

  test('can start recording via swipe gesture', async ({ mockedPage: page }) => {
    const switchEl = page.getByTestId('record-swipe-switch');
    const box = await switchEl.boundingBox();
    if (!box) throw new Error('Switch not found');

    await page.mouse.move(box.x + 36, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 36, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    await expect(page.getByTestId('record-duration')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('record-points')).toBeVisible();
  });

  test('accumulates points when location changes during recording', async ({
    mockedPage: page,
    context,
  }) => {
    const switchEl = page.getByTestId('record-swipe-switch');
    const box = await switchEl.boundingBox();
    if (!box) throw new Error('Switch not found');

    // Start recording
    await page.mouse.move(box.x + 36, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 36, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    await expect(page.getByTestId('record-points')).toBeVisible({ timeout: 5000 });

    // Simulate movement
    await simulateMovement(context, BUS_ROUTE_POINTS.slice(0, 4), 2500);

    const pointsText = await page.getByTestId('record-points').textContent();
    const points = parseInt(pointsText ?? '0', 10);
    expect(points).toBeGreaterThanOrEqual(1);
  });

  test('duration counter increments while recording', async ({ mockedPage: page }) => {
    const switchEl = page.getByTestId('record-swipe-switch');
    const box = await switchEl.boundingBox();
    if (!box) throw new Error('Switch not found');

    await page.mouse.move(box.x + 36, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 36, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    await expect(page.getByTestId('record-duration')).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(3000);
    const durationText = await page.getByTestId('record-duration').textContent();
    expect(durationText).not.toBe('0:00');
  });
});
