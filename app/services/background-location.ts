/**
 * Background location tracking for recording. Uses expo-task-manager + expo-location
 * so location updates continue when the app is minimized or screen is locked.
 */
import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import type { LocationPoint } from '@/services/api';
import {
  addLocationPoints,
  getInProgressRecording,
  touchRecording,
} from '@/services/recording-store';

const LOCATION_TASK_NAME = 'recording-background-location';

/** Emits when new points are added (for UI updates). Payload: count of new points. */
const listeners = new Set<(count: number) => void>();

export function onLocationBatch(callback: (count: number) => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function notifyListeners(count: number) {
  listeners.forEach((cb) => cb(count));
}

// Must be defined at top level - cannot be inside React lifecycle
TaskManager.defineTask<{ locations: Location.LocationObject[] }>(
  LOCATION_TASK_NAME,
  ({ data, error }) => {
    if (error) {
      console.error('Background location task error:', error.message);
      return Promise.resolve();
    }
    if (!data?.locations?.length) return Promise.resolve();

    const rec = getInProgressRecording();
    if (!rec) return Promise.resolve();

    const points: LocationPoint[] = data.locations.map((loc) => ({
      timestamp: new Date(loc.timestamp).toISOString(),
      latitude: loc.coords.latitude,
      longitude: loc.coords.longitude,
      altitude: loc.coords.altitude,
      speed: loc.coords.speed,
      bearing: loc.coords.heading,
      horizontal_accuracy: loc.coords.accuracy,
      vertical_accuracy: loc.coords.altitudeAccuracy,
    }));

    addLocationPoints(rec.id, points);
    touchRecording(rec.id);
    notifyListeners(points.length);
    return Promise.resolve();
  }
);

const LOCATION_INTERVAL_MS = 2000;
const DISTANCE_INTERVAL_M = 5;

/** Start background location updates. Call when recording starts. */
export async function startBackgroundLocation(): Promise<void> {
  const isRegistered = await Location.hasStartedLocationUpdatesAsync(
    LOCATION_TASK_NAME
  );
  if (isRegistered) return;

  await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
    accuracy: Location.Accuracy.BestForNavigation,
    timeInterval: LOCATION_INTERVAL_MS,
    distanceInterval: DISTANCE_INTERVAL_M,
    showsBackgroundLocationIndicator: true, // iOS blue pill when tracking
    // Required on Android: keeps location tracking alive when app is backgrounded
    foregroundService: {
      notificationTitle: 'Recording transit route',
      notificationBody: 'Location is being recorded in the background',
      notificationColor: '#09A6F3',
    },
  });
}

/** Stop background location updates. Call when recording stops. */
export async function stopBackgroundLocation(): Promise<void> {
  try {
    const isRegistered = await Location.hasStartedLocationUpdatesAsync(
      LOCATION_TASK_NAME
    );
    if (isRegistered) {
      await Location.stopLocationUpdatesAsync(LOCATION_TASK_NAME);
    }
  } catch (err) {
    console.error('Failed to stop background location:', err);
  }
}

/** Request background location permission. Returns true if granted. */
export async function requestBackgroundPermission(): Promise<boolean> {
  const { status } = await Location.requestBackgroundPermissionsAsync();
  return status === 'granted';
}

/** Check if foreground and background location permissions are granted. */
export async function checkLocationPermissions(): Promise<{
  foreground: boolean;
  background: boolean;
}> {
  const [fg, bg] = await Promise.all([
    Location.getForegroundPermissionsAsync(),
    Location.getBackgroundPermissionsAsync(),
  ]);
  return {
    foreground: fg.status === 'granted',
    background: bg.status === 'granted',
  };
}

/**
 * Refresh permission status using request APIs - use when returning from settings.
 * If already granted, request returns granted without showing a prompt.
 * This works around expo-location returning stale status from get*Async.
 */
export async function refreshPermissionsAfterSettingsReturn(): Promise<{
  foreground: boolean;
  background: boolean;
}> {
  const fg = await Location.requestForegroundPermissionsAsync();
  if (fg.status !== 'granted') {
    return { foreground: false, background: false };
  }
  const bg = await Location.requestBackgroundPermissionsAsync();
  return {
    foreground: true,
    background: bg.status === 'granted',
  };
}
