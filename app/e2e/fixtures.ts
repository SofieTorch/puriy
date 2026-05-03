import { test as base, expect, BrowserContext, Page } from '@playwright/test';
import { setupApiMocks } from './mocks';

/** Cochabamba center coordinates. */
export const COCHABAMBA = { latitude: -17.3895, longitude: -66.1568 };

/**
 * A sequence of coordinates along a typical bus route in Cochabamba.
 * Used to simulate movement during recording tests.
 */
export const BUS_ROUTE_POINTS = [
  { latitude: -17.3895, longitude: -66.1568 },
  { latitude: -17.3890, longitude: -66.1560 },
  { latitude: -17.3885, longitude: -66.1552 },
  { latitude: -17.3880, longitude: -66.1544 },
  { latitude: -17.3875, longitude: -66.1536 },
  { latitude: -17.3870, longitude: -66.1528 },
  { latitude: -17.3865, longitude: -66.1520 },
  { latitude: -17.3860, longitude: -66.1512 },
];

/**
 * Simulate movement along a route by updating geolocation at intervals.
 */
export async function simulateMovement(
  context: BrowserContext,
  points: { latitude: number; longitude: number }[],
  intervalMs = 2000,
): Promise<void> {
  for (const point of points) {
    await context.setGeolocation(point);
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

/**
 * Extended test fixture that sets up API mocks before each test.
 * Use `test` from this file instead of `@playwright/test` to get mocked APIs.
 */
export const test = base.extend<{ mockedPage: Page }>({
  mockedPage: async ({ page }, use) => {
    await setupApiMocks(page);
    await use(page);
  },
});

export { expect };
