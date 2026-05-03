/**
 * Local notifications for saved trips with a `departureTime`.
 *
 * Behaviour:
 *  - When the user saves a trip with a time, schedule a one-time
 *    (`one_time` trips) or daily-repeating (`commute` trips)
 *    notification that fires LEAD_MINUTES_BEFORE before the time.
 *  - At scheduling time we pre-fetch active detours for the bus lines
 *    in the trip and include them in the body. This is "fresh enough"
 *    because we also re-schedule everything on every app launch.
 *  - On app launch we cancel and re-schedule every saved trip — this
 *    catches detours added between launches without requiring a
 *    background task.
 *
 * Web fallback: expo-notifications is not functional on web, so all
 * scheduling functions are no-ops there. The Playwright e2e mocks the
 * scheduling call to assert it was invoked with the right arguments.
 */

import { Platform } from 'react-native';

import { api, DirectionsResponse } from '@/services/api';
import { getSavedTrips, parseRouteJson, SavedTrip } from '@/services/saved-trips';

type Notifications = typeof import('expo-notifications');

async function loadNotifications(): Promise<Notifications | null> {
  if (Platform.OS === 'web') return null;
  try {
    return await import('expo-notifications');
  } catch (err) {
    console.warn('[trip-notifications] expo-notifications not available:', err);
    return null;
  }
}

/** How many minutes before `departureTime` the notification fires. */
export const LEAD_MINUTES_BEFORE = 10;

/** Tag used in the notification's `data.kind` for filtering on tap. */
const KIND = 'saved_trip_departure';

interface LineDetour {
  line_name: string;
  reason: string | null;
}

export interface NotificationContent {
  title: string;
  body: string;
  data: {
    kind: typeof KIND;
    saved_trip_id: number;
    line_ids: string[];
  };
}

/**
 * Build the notification body. Pure function — testable in isolation.
 *
 * Examples:
 *  - No detours:     "Tu viaje a Plaza Colón sale a las 07:30. Toma la
 *                     Línea 101."
 *  - With a detour:  "Tu viaje a Plaza Colón sale a las 07:30. Toma la
 *                     Línea 101 — ⚠ Desvío activo: Construcción."
 */
export function buildNotificationContent(
  trip: SavedTrip,
  detours: LineDetour[],
): NotificationContent {
  const route = parseRouteJson(trip);
  const busLegs = route.legs.filter((l) => l.mode === 'bus' && l.line_name);
  const lineIds = busLegs
    .map((l) => l.line_id)
    .filter((id): id is string => id != null);
  const lineNames = busLegs.map((l) => l.line_name).filter((n): n is string => !!n);
  const uniqueLines = Array.from(new Set(lineNames));

  const title = `Salida a ${trip.destName} a las ${trip.departureTime}`;
  let body = uniqueLines.length === 1
    ? `Toma la Línea ${uniqueLines[0]}.`
    : `Toma: ${uniqueLines.map((n) => `Línea ${n}`).join(' → ')}.`;

  if (detours.length > 0) {
    const summary = detours
      .map((d) => `Línea ${d.line_name}${d.reason ? ` (${d.reason})` : ''}`)
      .join(', ');
    body += ` ⚠ Desvío activo: ${summary}.`;
  }

  return {
    title,
    body,
    data: { kind: KIND, saved_trip_id: trip.id, line_ids: lineIds },
  };
}

/** Parse "HH:mm" → {hour, minute}; throws on invalid input. */
function parseDepartureTime(time: string): { hour: number; minute: number } {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(time.trim());
  if (!m) throw new Error(`invalid departure time: ${time}`);
  return { hour: Number(m[1]), minute: Number(m[2]) };
}

/**
 * Compute the next firing Date for a given departure time, accounting
 * for the lead time. Pure function — `now` is injectable for testing.
 *
 *  - If today's lead-time has not yet passed, fires today at
 *    (departure - LEAD_MINUTES_BEFORE).
 *  - Otherwise fires tomorrow at the same offset.
 */
export function nextFireDate(
  departureTime: string,
  now: Date = new Date(),
): Date {
  const { hour, minute } = parseDepartureTime(departureTime);
  const fire = new Date(now);
  fire.setHours(hour, minute, 0, 0);
  fire.setMinutes(fire.getMinutes() - LEAD_MINUTES_BEFORE);
  if (fire.getTime() <= now.getTime()) {
    fire.setDate(fire.getDate() + 1);
  }
  return fire;
}

async function fetchDetoursForLines(lineIds: string[]): Promise<LineDetour[]> {
  const results: LineDetour[] = [];
  for (const lineId of lineIds) {
    try {
      const detour = await api.getActiveDetour(lineId);
      if (detour) {
        results.push({
          line_name: detour.line_name ?? lineId,
          reason: detour.reason ?? null,
        });
      }
    } catch {
      // Best effort — failures during scheduling shouldn't crash.
    }
  }
  return results;
}

/** Identifier under which we register this trip's scheduled notification. */
function tripIdentifier(tripId: number): string {
  return `saved-trip-${tripId}`;
}

/**
 * Schedule (or replace) the local notification for one trip. No-op on
 * web and when `departureTime` is empty. Best-effort: errors are logged.
 */
export async function scheduleTripNotification(trip: SavedTrip): Promise<void> {
  if (!trip.departureTime) return;
  const N = await loadNotifications();
  if (!N) return;

  try {
    const route: DirectionsResponse = parseRouteJson(trip);
    const busLineIds = route.legs
      .filter((l) => l.mode === 'bus' && l.line_id)
      .map((l) => l.line_id as string);
    const detours = await fetchDetoursForLines(busLineIds);
    const content = buildNotificationContent(trip, detours);

    // Replace any prior schedule for the same trip.
    await N.cancelScheduledNotificationAsync(tripIdentifier(trip.id))
      .catch(() => undefined);

    if (trip.type === 'commute') {
      const { hour, minute } = parseDepartureTime(trip.departureTime);
      // Calendar trigger fires every day at the same time (lead minutes
      // before the departure). Bolivia has no DST so the wall clock is
      // stable.
      const fireMinute = (minute - LEAD_MINUTES_BEFORE + 60) % 60;
      const fireHour = (hour + Math.floor((minute - LEAD_MINUTES_BEFORE) / 60) + 24) % 24;
      await N.scheduleNotificationAsync({
        identifier: tripIdentifier(trip.id),
        content,
        trigger: {
          type: N.SchedulableTriggerInputTypes.CALENDAR,
          hour: fireHour,
          minute: fireMinute,
          repeats: true,
        },
      });
    } else {
      await N.scheduleNotificationAsync({
        identifier: tripIdentifier(trip.id),
        content,
        trigger: {
          type: N.SchedulableTriggerInputTypes.DATE,
          date: nextFireDate(trip.departureTime),
        },
      });
    }
  } catch (err) {
    console.warn('[trip-notifications] schedule failed:', err);
  }
}

/** Cancel a previously scheduled trip notification. No-op on web / if absent. */
export async function cancelTripNotification(tripId: number): Promise<void> {
  const N = await loadNotifications();
  if (!N) return;
  try {
    await N.cancelScheduledNotificationAsync(tripIdentifier(tripId));
  } catch {
    // ignore
  }
}

/**
 * Cancel everything we scheduled and re-schedule from scratch. Called
 * once on app boot so detours added between sessions get reflected in
 * notification bodies.
 */
export async function rescheduleAllSavedTrips(): Promise<void> {
  if (Platform.OS === 'web') return;
  try {
    const trips = getSavedTrips().filter((t) => t.departureTime);
    for (const trip of trips) {
      await scheduleTripNotification(trip);
    }
  } catch (err) {
    console.warn('[trip-notifications] reschedule-all failed:', err);
  }
}
