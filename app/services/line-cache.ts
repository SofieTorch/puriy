/**
 * Line cache - fetch from API when online, serve from local DB when offline.
 */
import { eq } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import { lines as linesTable } from '@/db/schema';
import api, { type Line } from '@/services/api';
import NetInfo from '@react-native-community/netinfo';

/** Get lines: from API when online (and refresh cache), from cache when offline.
 *  Includes both approved and pending lines so contributors can assign recordings to pending lines.
 */
export async function getLines(): Promise<Line[]> {
  const netInfo = await NetInfo.fetch();
  const isOnline = netInfo.isConnected ?? false;

  if (isOnline) {
    try {
      const [approved, pending] = await Promise.all([
        api.getLines('approved'),
        api.getLines('pending'),
      ]);
      const all = [...approved, ...pending];
      await refreshLineCache(all);
      return all;
    } catch (err) {
      console.warn('Failed to fetch lines, using cache:', err);
      return getLinesFromCache();
    }
  }

  return getLinesFromCache();
}

/** Refresh the local line cache. */
export async function refreshLineCache(lines: Line[]): Promise<void> {
  const now = new Date().toISOString();
  for (const line of lines) {
    getDb().insert(linesTable)
      .values({
        id: line.id,
        name: line.name,
        description: line.description,
        status: line.status,
        createdAt: line.created_at,
        updatedAt: line.updated_at,
        cachedAt: now,
      })
      .onConflictDoUpdate({
        target: linesTable.id,
        set: {
          name: line.name,
          description: line.description,
          status: line.status,
          createdAt: line.created_at,
          updatedAt: line.updated_at,
          cachedAt: now,
        },
      })
      .run();
  }
}

/** Get lines from local cache (offline). */
export async function getLinesFromCache(): Promise<Line[]> {
  const rows = getDb().select().from(linesTable).all();
  return rows.map((r) => ({
    id: r.id,
    name: r.name,
    description: r.description,
    status: r.status as Line['status'],
    created_at: r.createdAt,
    updated_at: r.updatedAt,
  }));
}
