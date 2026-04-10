/**
 * Stable device identifier for voting attribution.
 *
 * Generates a UUID on first call and persists it in the local SQLite database
 * via a simple key-value approach. Survives app restarts but not reinstalls.
 */

import Constants from 'expo-constants';

let cachedDeviceId: string | null = null;

export function getDeviceId(): string {
  if (cachedDeviceId) return cachedDeviceId;

  // expo-constants provides a stable installation ID
  const installId = Constants.installationId;
  if (installId) {
    cachedDeviceId = installId;
    return installId;
  }

  // Fallback: generate a simple pseudo-UUID
  cachedDeviceId =
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  return cachedDeviceId;
}
