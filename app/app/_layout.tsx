import { DefaultTheme, ThemeProvider, type Theme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { LogBox } from 'react-native';
import { useEffect } from 'react';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
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
import { applyInterFont, interFontMap } from '@/constants/fonts';
import { palette } from '@/constants/palette';
import { initPushNotifications } from '@/services/push';
import { rescheduleAllSavedTrips } from '@/services/trip-notifications';
import '@/global.css';

// Keep the splash up until Inter loads; patch Text to use it before any render.
SplashScreen.preventAutoHideAsync().catch(() => {});
applyInterFont();

const LightTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: palette.bg,
    primary: palette.blue.DEFAULT,
    text: palette.ink,
    border: palette.line,
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
  const [fontsLoaded, fontError] = useFonts(interFontMap);
  const fontsReady = fontsLoaded || fontError != null;

  useEffect(() => {
    if (fontsReady) SplashScreen.hideAsync().catch(() => {});
  }, [fontsReady]);

  // Hold on the splash only briefly; if the font fails, fall back to system.
  if (!fontsReady) return null;

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
            <StatusBar style="light" backgroundColor={palette.blue.DEFAULT} />
          </ThemeProvider>
        </DatabaseProvider>
      </GestureHandlerRootView>
    </GluestackUIProvider>

  );
}
