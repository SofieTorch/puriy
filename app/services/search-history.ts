/**
 * Search history — remembers recently picked locations for quick re-use.
 * Keeps the most recent 20 entries, deduplicated by name.
 */

import { desc, eq } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import { searchHistory, SearchHistoryEntry } from '@/db/schema';

const MAX_ENTRIES = 20;

export function addToHistory(name: string, lon: number, lat: number): void {
  const db = getDb();

  // Update timestamp if already exists (move to top)
  const existing = db
    .select()
    .from(searchHistory)
    .where(eq(searchHistory.name, name))
    .get();

  if (existing) {
    db.update(searchHistory)
      .set({ lon, lat, usedAt: new Date().toISOString() })
      .where(eq(searchHistory.id, existing.id))
      .run();
    return;
  }

  // Insert new entry
  db.insert(searchHistory)
    .values({ name, lon, lat, usedAt: new Date().toISOString() })
    .run();

  // Trim to MAX_ENTRIES
  const all = db
    .select({ id: searchHistory.id })
    .from(searchHistory)
    .orderBy(desc(searchHistory.usedAt))
    .all();

  if (all.length > MAX_ENTRIES) {
    const toDelete = all.slice(MAX_ENTRIES);
    for (const row of toDelete) {
      db.delete(searchHistory).where(eq(searchHistory.id, row.id)).run();
    }
  }
}

export function getHistory(): SearchHistoryEntry[] {
  return getDb()
    .select()
    .from(searchHistory)
    .orderBy(desc(searchHistory.usedAt))
    .all();
}

export function filterHistory(query: string): SearchHistoryEntry[] {
  if (query.length === 0) return getHistory();
  const lower = query.toLowerCase();
  return getHistory().filter((e) => e.name.toLowerCase().includes(lower));
}
