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
 * DatabaseProvider so `getDb()` works.
 */
function PostBootEffects() {
  useEffect(() => {
    void rescheduleAllSavedTrips();
  }, []);
  return null;
}

export default function RootLayout() {
  useEffect(() => {
    void initPushNotifications();
  }, []);

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
