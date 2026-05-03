/**
 * Saved trips service — store and retrieve favorite routes from local SQLite.
 *
 * "commute" trips also drive push subscriptions: every time the set of
 * commute trips changes we PUT the union of their bus-line ids to
 * `/devices/{id}/subscriptions` so the server knows which detours to
 * notify this device about.
 */

import { eq } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import { savedTrips, SavedTrip } from '@/db/schema';
import { api, DirectionsResponse } from '@/services/api';
import { getDeviceId } from '@/services/device-id';

export type TripType = 'one_time' | 'commute';

export interface SaveTripParams {
  originName: string;
  destName: string;
  originCoords: [number, number]; // [lon, lat]
  destCoords: [number, number];
  type: TripType;
  route: DirectionsResponse;
  /** Optional HH:mm in local time. When set, a notification is scheduled. */
  departureTime?: string | null;
}

export function saveTrip(params: SaveTripParams): SavedTrip {
  // We avoid `.returning().get()` here — on the web (`expo-sqlite/web`)
  // it round-trips the inserted row through a JSON envelope that chokes
  // on certain text payloads (notably the serialised route_json). Doing
  // a separate SELECT by lastInsertRowId is uniform across native + web.
  const insert = getDb()
    .insert(savedTrips)
    .values({
      originName: params.originName,
      destName: params.destName,
      originLon: params.originCoords[0],
      originLat: params.originCoords[1],
      destLon: params.destCoords[0],
      destLat: params.destCoords[1],
      type: params.type,
      routeJson: JSON.stringify(params.route),
      departureTime: params.departureTime ?? null,
      createdAt: new Date().toISOString(),
    })
    .run();
  const insertedId = Number(insert.lastInsertRowId);
  const result = getDb()
    .select()
    .from(savedTrips)
    .where(eq(savedTrips.id, insertedId))
    .get()!;

  // Saving a commute trip can change the line-subscription set.
  if (params.type === 'commute') {
    void syncCommuteSubscriptions();
  }

  // Schedule a local notification if the user provided a departure time.
  // Imported lazily to avoid pulling expo-notifications into web bundles
  // that don't need it.
  if (result.departureTime) {
    void import('@/services/trip-notifications').then((m) =>
      m.scheduleTripNotification(result),
    );
  }

  return result;
}

export function getSavedTrips(): SavedTrip[] {
  return getDb().select().from(savedTrips).all();
}

/**
 * Get trips to display today:
 * - All commute trips (shown every day)
 * - One-time trips created today only
 */
export function getTodayTrips(): SavedTrip[] {
  const all = getSavedTrips();
  const today = new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"

  return all.filter((trip) => {
    if (trip.type === 'commute') return true;
    return trip.createdAt.slice(0, 10) === today;
  });
}

export function deleteTrip(id: number): void {
  // Look up the trip first so we know whether to resync subscriptions and
  // whether there's a scheduled notification to cancel.
  const before = getDb()
    .select()
    .from(savedTrips)
    .where(eq(savedTrips.id, id))
    .get();

  getDb().delete(savedTrips).where(eq(savedTrips.id, id)).run();

  if (before?.type === 'commute') {
    void syncCommuteSubscriptions();
  }

  if (before?.departureTime) {
    void import('@/services/trip-notifications').then((m) =>
      m.cancelTripNotification(id),
    );
  }
}

export function parseRouteJson(trip: SavedTrip): DirectionsResponse {
  return JSON.parse(trip.routeJson) as DirectionsResponse;
}

/** Distinct bus-line ids referenced by a saved trip's directions. */
function lineIdsInTrip(trip: SavedTrip): string[] {
  const route = parseRouteJson(trip);
  const ids = new Set<string>();
  for (const leg of route.legs ?? []) {
    if (leg.mode === 'bus' && leg.line_id) ids.add(leg.line_id);
  }
  return [...ids];
}

/**
 * PUT this device's commute subscriptions = union of bus-line ids across
 * all commute saved trips. Best effort: failures are logged, not rethrown.
 */
export async function syncCommuteSubscriptions(): Promise<void> {
  try {
    const commuteTrips = getSavedTrips().filter((t) => t.type === 'commute');
    const allLineIds = new Set<string>();
    for (const trip of commuteTrips) {
      for (const lineId of lineIdsInTrip(trip)) {
        allLineIds.add(lineId);
      }
    }
    await api.replaceCommuteSubscriptions(getDeviceId(), [...allLineIds]);
  } catch (err) {
    console.warn('[saved-trips] subscription sync failed:', err);
  }
}
