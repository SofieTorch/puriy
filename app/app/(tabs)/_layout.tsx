import { Tabs } from 'expo-router';
import React from 'react';
import { View } from 'react-native';

import { HapticTab } from '@/components/haptic-tab';
import { HeaderStatusBadge, HeaderIcon } from '@/components/header';
import { palette } from '@/constants/palette';
import Feather from '@expo/vector-icons/Feather';
import { MaterialIcons } from '@expo/vector-icons';

export default function TabLayout() {
  const inactiveBlue = palette.hint;
  const activeBlue = palette.blue.DEFAULT;

  const renderTabIcon = (icon: React.ReactNode) => (
    <View style={{ alignItems: 'center', justifyContent: 'center' }}>{icon}</View>
  );

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: activeBlue,
        tabBarInactiveTintColor: inactiveBlue,
        headerShown: true,
        headerStyle: { backgroundColor: '#3D6CB4' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: '500', fontSize: 20 },
        headerLeft: () => <HeaderStatusBadge />,
        headerRight: () => <HeaderIcon />,
        tabBarButton: HapticTab,
        tabBarShowLabel: true,
        tabBarLabelPosition: 'below-icon',
        tabBarItemStyle: {
          justifyContent: 'center',
        },
        tabBarStyle: {
          height: 120,
          paddingTop: 12,
          paddingBottom: 12,
          borderTopWidth: 0,
          borderTopLeftRadius: 28,
          borderTopRightRadius: 28,
          backgroundColor: '#FFFFFF',
          position: 'absolute',
          shadowColor: '#000',
          shadowOpacity: 0.08,
          shadowRadius: 14,
          shadowOffset: { width: 0, height: -4 },
          elevation: 10,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          lineHeight: 13,
          marginTop: 6,
          marginBottom: 2,
        },
      }}>
      <Tabs.Screen
        name="explore"
        options={{
          title: 'Explorar',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="map-pin" color={color} />),
          tabBarLabel: 'Explorar',
        }}
      />
      <Tabs.Screen
        name="record"
        options={{
          title: 'Trayecto',
          tabBarLabel: 'Trazar',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="navigation" color={color} />),
        }}
      />
      <Tabs.Screen
        name="contribute"
        options={{
          title: 'Contribuir',
          tabBarLabel: 'Contribuir',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(
              <MaterialIcons size={28} name="playlist-add" color={color} />
            ),
        }}
      />
      <Tabs.Screen
        name="favorites"
        options={{
          title: 'Favoritos',
          tabBarLabel: 'Favoritos',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="star" color={color} />),
        }}
      />
    </Tabs>
  );
}
