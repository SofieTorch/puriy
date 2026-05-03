/**
 * Stable device identifier for crowdsourced contributions.
 *
 * Generates a UUID on first call and persists it in the local SQLite
 * database (`preferences` table, key `device_id`). Survives app
 * restarts but not reinstalls. Cached in memory after the first DB hit.
 *
 * In E2E test mode, returns the deterministic ID from
 * `EXPO_PUBLIC_E2E_DEVICE_ID` and skips persistence — keeps mocked
 * server fixtures working without DB writes.
 */

import { eq } from 'drizzle-orm';

import { preferences } from '@/db/schema';
import { getDb } from '@/lib/db';

const E2E_DEVICE_ID = process.env.EXPO_PUBLIC_E2E_DEVICE_ID ?? null;
const DEVICE_ID_KEY = 'device_id';

let cachedDeviceId: string | null = null;

function generateUuid(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getDeviceId(): string {
  if (E2E_DEVICE_ID) return E2E_DEVICE_ID;
  if (cachedDeviceId) return cachedDeviceId;

  const db = getDb();
  const row = db
    .select()
    .from(preferences)
    .where(eq(preferences.key, DEVICE_ID_KEY))
    .get();

  if (row) {
    cachedDeviceId = row.value;
    return row.value;
  }

  const newId = generateUuid();
  db.insert(preferences).values({ key: DEVICE_ID_KEY, value: newId }).run();
  cachedDeviceId = newId;
  return newId;
}
