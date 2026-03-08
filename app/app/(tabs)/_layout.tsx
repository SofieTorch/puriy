import { Tabs } from 'expo-router';
import React from 'react';
import { View } from 'react-native';

import { HapticTab } from '@/components/haptic-tab';
import Feather from '@expo/vector-icons/Feather';
import { MaterialIcons } from '@expo/vector-icons';

export default function TabLayout() {
  const inactiveBlue = '#67CCFF';
  const activeBlue = '#009DFF';

  const renderTabIcon = (icon: React.ReactNode) => (
    <View style={{ alignItems: 'center', justifyContent: 'center' }}>{icon}</View>
  );

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: activeBlue,
        tabBarInactiveTintColor: inactiveBlue,
        headerShown: false,
        tabBarButton: HapticTab,
        tabBarShowLabel: true,
        tabBarLabelPosition: 'below-icon',
        tabBarItemStyle: {
          height: 84,
          justifyContent: 'center',
          paddingTop: 0,
          paddingBottom: 0,
        },
        tabBarIconStyle: {
          marginTop: 6,
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
          overflow: 'visible',
          shadowColor: '#000',
          shadowOpacity: 0.08,
          shadowRadius: 14,
          shadowOffset: { width: 0, height: -4 },
          elevation: 10,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '700',
          lineHeight: 13,
          marginTop: 6,
          marginBottom: 2,
        },
      }}>
      <Tabs.Screen
        name="explore"
        options={{
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="map-pin" color={color} />),
          tabBarLabel: 'Explorar',
        }}
      />
      <Tabs.Screen
        name="record"
        options={{
          tabBarLabel: 'Trazar',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="navigation" color={color} />),
        }}
      />
      <Tabs.Screen
        name="contribute"
        options={{
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
          tabBarLabel: 'Favoritos',
          tabBarIcon: ({ color }: { color: string }) =>
            renderTabIcon(<Feather size={28} name="star" color={color} />),
        }}
      />
    </Tabs>
  );
}
