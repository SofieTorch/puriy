/**
 * Local preferences service — key-value store backed by SQLite.
 */

import { getDb } from '@/lib/db';
import { preferences } from '@/db/schema';
import { eq } from 'drizzle-orm';

export function getPreference(key: string, defaultValue: string): string {
  const row = getDb().select().from(preferences).where(eq(preferences.key, key)).get();
  return row?.value ?? defaultValue;
}

export function setPreference(key: string, value: string): void {
  const existing = getDb().select().from(preferences).where(eq(preferences.key, key)).get();
  if (existing) {
    getDb().update(preferences).set({ value }).where(eq(preferences.key, key)).run();
  } else {
    getDb().insert(preferences).values({ key, value }).run();
  }
}

// ---------------------------------------------------------------------------
// Convenience helpers
// ---------------------------------------------------------------------------

export function includePendingLines(): boolean {
  return getPreference('include_pending_lines', 'false') === 'true';
}

export function setIncludePendingLines(value: boolean): void {
  setPreference('include_pending_lines', value ? 'true' : 'false');
}

export function includePendingRoutes(): boolean {
  return getPreference('include_pending_routes', 'false') === 'true';
}

export function setIncludePendingRoutes(value: boolean): void {
  setPreference('include_pending_routes', value ? 'true' : 'false');
}
