import BottomSheet, { BottomSheetBackdrop, BottomSheetView } from '@gorhom/bottom-sheet';
import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import React, { forwardRef, useCallback, useMemo, useState } from 'react';
import { Switch, Text, View } from 'react-native';

import {
  includePendingLines,
  includePendingRoutes,
  setIncludePendingLines,
  setIncludePendingRoutes,
} from '@/services/preferences';

const BLUE = '#09A6F3';

const PreferencesSheet = forwardRef<BottomSheet>((_, ref) => {
  const tabBarHeight = useBottomTabBarHeight();

  const renderBackdrop = useCallback(
    (props: any) => (
      <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} pressBehavior="close" />
    ),
    []
  );

  const [pendingLines, setPendingLines] = useState(() => includePendingLines());
  const [pendingRoutes, setPendingRoutes] = useState(() => includePendingRoutes());

  const togglePendingLines = useCallback(
    (value: boolean) => {
      setPendingLines(value);
      setIncludePendingLines(value);
    },
    []
  );

  const togglePendingRoutes = useCallback(
    (value: boolean) => {
      setPendingRoutes(value);
      setIncludePendingRoutes(value);
    },
    []
  );

  return (
    <BottomSheet
      ref={ref}
      index={-1}
      enableDynamicSizing
      enablePanDownToClose
      enableContentPanningGesture={false}
      backdropComponent={renderBackdrop}
      backgroundStyle={{ borderRadius: 24 }}
      handleIndicatorStyle={{ backgroundColor: '#D1D5DB', width: 40 }}
      containerStyle={{ zIndex: 1000 }}
    >
      <BottomSheetView testID="prefs-sheet" className="flex-1 px-6 pt-2" style={{ paddingBottom: tabBarHeight + 12 }}>
        <View testID="prefs-title">
          <Text className="mb-5 text-lg font-semibold text-gray-800">
            Preferencias
          </Text>
        </View>

        <View className="mb-4 flex-row items-center justify-between">
          <View testID="prefs-pending-lines" className="flex-1 pr-4">
            <Text className="text-base text-gray-700">
              Incluir líneas pendientes
            </Text>
            <Text className="text-sm text-gray-400">
              Mostrar líneas que aún no fueron aprobadas por la comunidad
            </Text>
          </View>
          <Switch
            testID="prefs-pending-lines-switch"
            value={pendingLines}
            onValueChange={togglePendingLines}
            trackColor={{ false: '#D1D5DB', true: BLUE }}
            thumbColor="#fff"
          />
        </View>

        <View className="flex-row items-center justify-between">
          <View className="flex-1 pr-4">
            <Text className="text-base text-gray-700">
              Incluir rutas pendientes
            </Text>
            <Text className="text-sm text-gray-400">
              Mostrar rutas con segmentos aún en proceso de votación
            </Text>
          </View>
          <Switch
            testID="prefs-pending-routes-switch"
            value={pendingRoutes}
            onValueChange={togglePendingRoutes}
            trackColor={{ false: '#D1D5DB', true: BLUE }}
            thumbColor="#fff"
          />
        </View>
      </BottomSheetView>
    </BottomSheet>
  );
});

PreferencesSheet.displayName = 'PreferencesSheet';

export default PreferencesSheet;
