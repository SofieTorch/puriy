/**
 * Foreground location service.
 * Uses watchPositionAsync for real-time updates.
 */

import * as Location from 'expo-location';

let cachedLocation: { lon: number; lat: number } | null = null;
let watchSubscription: Location.LocationSubscription | null = null;
const listeners: Set<(loc: { lon: number; lat: number }) => void> = new Set();

/**
 * Get the current location once (always fresh, no cache).
 */
export async function getCurrentLocation(): Promise<{ lon: number; lat: number } | null> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') return null;

    const position = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Highest,
      mayShowUserSettingsDialog: true,
    });
    cachedLocation = { lon: position.coords.longitude, lat: position.coords.latitude };
    return cachedLocation;
  } catch {
    return cachedLocation;
  }
}

/**
 * Subscribe to continuous location updates.
 * Returns an unsubscribe function.
 */
export async function watchLocation(
  callback: (loc: { lon: number; lat: number }) => void
): Promise<() => void> {
  listeners.add(callback);

  // Send cached immediately if available
  if (cachedLocation) callback(cachedLocation);

  // Start watching if not already
  if (!watchSubscription) {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status === 'granted') {
      watchSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Highest,
          distanceInterval: 0, // fire on ANY change (important for emulator)
          timeInterval: 3_000, // poll every 3s
        },
        (position) => {
          cachedLocation = { lon: position.coords.longitude, lat: position.coords.latitude };
          for (const fn of listeners) fn(cachedLocation);
        }
      );
    }
  }

  return () => {
    listeners.delete(callback);
    if (listeners.size === 0 && watchSubscription) {
      watchSubscription.remove();
      watchSubscription = null;
    }
  };
}

export function getCachedLocation(): { lon: number; lat: number } | null {
  return cachedLocation;
}
