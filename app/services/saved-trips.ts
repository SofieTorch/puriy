/**
 * Saved trips service — store and retrieve favorite routes from local SQLite.
 */

import { eq, and } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import { savedTrips, SavedTrip } from '@/db/schema';
import { DirectionsResponse } from '@/services/api';

export type TripType = 'one_time' | 'commute';

export interface SaveTripParams {
  originName: string;
  destName: string;
  originCoords: [number, number]; // [lon, lat]
  destCoords: [number, number];
  type: TripType;
  route: DirectionsResponse;
}

export function saveTrip(params: SaveTripParams): SavedTrip {
  const result = getDb()
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
      createdAt: new Date().toISOString(),
    })
    .returning()
    .get();

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
  getDb().delete(savedTrips).where(eq(savedTrips.id, id)).run();
}

export function parseRouteJson(trip: SavedTrip): DirectionsResponse {
  return JSON.parse(trip.routeJson) as DirectionsResponse;
}
