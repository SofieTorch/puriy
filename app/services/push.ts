/**
 * Push notification setup.
 *
 * Called once on app launch (from RootLayout). Always calls
 * `/devices/register` — even when the user denied notification permission
 * — so that the device row exists in the server's `devices` table and any
 * subsequent FK-constrained write (recordings, votes, fares) succeeds.
 *
 * If permission was granted and we're on a real device, we also obtain an
 * Expo push token and pass it along, then install a tap handler that deep
 * links into the relevant line/explore screen.
 *
 * `expo-notifications` is dynamically imported only on iOS/Android — on
 * web it triggers `localStorage` access at module load (Expo Router SSRs
 * the entry chunk and `localStorage` doesn't exist on the server side).
 */

import { Platform } from 'react-native';
import { router } from 'expo-router';

import { api } from '@/services/api';
import { getDeviceId } from '@/services/device-id';

let initialized = false;
let tapSubscription: { remove(): void } | null = null;

type Notifications = typeof import('expo-notifications');

async function loadNotifications(): Promise<Notifications | null> {
  if (Platform.OS === 'web') return null;
  try {
    return await import('expo-notifications');
  } catch (err) {
    console.warn('[push] expo-notifications not available:', err);
    return null;
  }
}

/** Best-effort idempotent setup. Safe to call multiple times. */
export async function initPushNotifications(): Promise<void> {
  if (initialized) return;
  initialized = true;

  const deviceId = getDeviceId();
  const platform: 'ios' | 'android' | null =
    Platform.OS === 'ios' ? 'ios' : Platform.OS === 'android' ? 'android' : null;

  if (platform === null) {
    // Web / unsupported — register without a token so the FK still resolves.
    await safeRegister(deviceId, null, 'android');
    return;
  }

  // tryGetPushToken returns null on simulators / when permission is denied.
  // Registration always proceeds either way.
  const expoToken = await tryGetPushToken();
  await safeRegister(deviceId, expoToken, platform);

  if (expoToken) {
    await installTapHandler();
  }
}

async function tryGetPushToken(): Promise<string | null> {
  const N = await loadNotifications();
  if (!N) return null;
  try {
    const existing = await N.getPermissionsAsync();
    let granted = existing.granted;
    if (!granted && existing.canAskAgain) {
      const requested = await N.requestPermissionsAsync();
      granted = requested.granted;
    }
    if (!granted) return null;

    const result = await N.getExpoPushTokenAsync();
    return result.data ?? null;
  } catch (err) {
    console.warn('[push] could not obtain Expo token:', err);
    return null;
  }
}

async function safeRegister(
  deviceId: string,
  expoToken: string | null,
  platform: 'ios' | 'android',
): Promise<void> {
  try {
    await api.registerDevice({ deviceId, expoToken, platform });
  } catch (err) {
    // Registration failure must not block the app from running offline-first.
    console.warn('[push] /devices/register failed:', err);
  }
}

async function installTapHandler(): Promise<void> {
  if (tapSubscription) return;
  const N = await loadNotifications();
  if (!N) return;
  tapSubscription = N.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data as
      | { kind?: string; line_id?: string }
      | undefined;
    if (data?.line_id) {
      // Deep link to the explore tab focused on this line.
      router.push({ pathname: '/explore', params: { lineId: data.line_id } });
    }
  });
}
