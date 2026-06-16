import { DefaultTheme, ThemeProvider, type Theme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { LogBox } from 'react-native';
import { useEffect } from 'react';
import 'react-native-reanimated';

if (process.env.EXPO_PUBLIC_E2E === 'true') {
  LogBox.ignoreAllLogs(true);
}

// Expo Go on Android (SDK 53+) prints this natively because remote push was
// removed from Expo Go — it's harmless for local dev (we register tokenless and
// use a development build for real push). Silence the noise so it stops nagging.
LogBox.ignoreLogs([
  /Android Push notifications.*removed from Expo Go/,
  'expo-notifications',
]);

import { DatabaseProvider } from '@/components/DatabaseProvider';
import { GluestackUIProvider } from '@/components/ui/gluestack-ui-provider';
import { initPushNotifications } from '@/services/push';
import { rescheduleAllSavedTrips } from '@/services/trip-notifications';
import '@/global.css';

const LightTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: '#FFFDF7',
    primary: '#09A6F3',
  },
};

export const unstable_settings = {
  anchor: '(tabs)',
};

/**
 * Effects that need the local DB to be initialized — mounted under
 * DatabaseProvider so `getDb()` works. `SQLiteProvider` opens the database
 * asynchronously, so anything that reaches `getDb()` (push registration reads
 * the device id from SQLite) must run here, not in RootLayout's effect, or it
 * fires before the db ref is set and throws "Database not initialized".
 */
function PostBootEffects() {
  useEffect(() => {
    void rescheduleAllSavedTrips();
    void initPushNotifications();
  }, []);
  return null;
}

export default function RootLayout() {
  return (

    <GluestackUIProvider mode="light">
      <GestureHandlerRootView style={{ flex: 1 }}>
        <DatabaseProvider>
          <PostBootEffects />
          <ThemeProvider value={LightTheme}>
            <Stack>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
            </Stack>
            <StatusBar style="light" backgroundColor="#09A6F3" />
          </ThemeProvider>
        </DatabaseProvider>
      </GestureHandlerRootView>
    </GluestackUIProvider>

  );
}
