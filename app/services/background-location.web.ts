/**
 * Web shim for background location tracking.
 * On web there's no background task API, so we use foreground watchPosition
 * via expo-location's built-in web shim (which wraps navigator.geolocation).
 * This works well with Playwright's context.setGeolocation() for e2e tests.
 */
import * as Location from 'expo-location';
import type { LocationPoint } from '@/services/api';
import {
  addLocationPoints,
  getInProgressRecording,
  touchRecording,
} from '@/services/recording-store';

const listeners = new Set<(count: number) => void>();

export function onLocationBatch(callback: (count: number) => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function notifyListeners(count: number) {
  listeners.forEach((cb) => cb(count));
}

let watchSubscription: Location.LocationSubscription | null = null;

/** Start foreground location watching (web substitute for background tracking). */
export async function startBackgroundLocation(): Promise<void> {
  if (watchSubscription) return;

  watchSubscription = await Location.watchPositionAsync(
    {
      accuracy: Location.Accuracy.BestForNavigation,
      distanceInterval: 5,
      timeInterval: 2000,
    },
    (location) => {
      const rec = getInProgressRecording();
      if (!rec) return;

      const point: LocationPoint = {
        timestamp: new Date(location.timestamp).toISOString(),
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        altitude: location.coords.altitude,
        speed: location.coords.speed,
        bearing: location.coords.heading,
        horizontal_accuracy: location.coords.accuracy,
        vertical_accuracy: location.coords.altitudeAccuracy,
      };

      addLocationPoints(rec.id, [point]);
      touchRecording(rec.id);
      notifyListeners(1);
    }
  );
}

/** Stop foreground location watching. */
export async function stopBackgroundLocation(): Promise<void> {
  if (watchSubscription) {
    watchSubscription.remove();
    watchSubscription = null;
  }
}

/** Request background location permission. On web, foreground permission is sufficient. */
export async function requestBackgroundPermission(): Promise<boolean> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  return status === 'granted';
}

/** Check location permissions. On web, background = foreground (no distinction). */
export async function checkLocationPermissions(): Promise<{
  foreground: boolean;
  background: boolean;
}> {
  const fg = await Location.getForegroundPermissionsAsync();
  const granted = fg.status === 'granted';
  return { foreground: granted, background: granted };
}

/** Refresh permissions. On web, just re-checks foreground permission. */
export async function refreshPermissionsAfterSettingsReturn(): Promise<{
  foreground: boolean;
  background: boolean;
}> {
  const fg = await Location.requestForegroundPermissionsAsync();
  const granted = fg.status === 'granted';
  return { foreground: granted, background: granted };
}
