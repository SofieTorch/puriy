import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import Feather from '@expo/vector-icons/Feather';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import RouteMap, { Leg } from '@/components/route-map';
import { SavedTrip } from '@/db/schema';
import { DirectionsResponse } from '@/services/api';
import { getCurrentLocation } from '@/services/current-location';
import { reverseGeocode } from '@/services/geocoding';
import { deleteTrip, getTodayTrips, parseRouteJson } from '@/services/saved-trips';

const BLUE = '#09A6F3';

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function formatDuration(s: number): string {
  const mins = Math.round(s / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

function busLines(route: DirectionsResponse): string[] {
  const names: string[] = [];
  for (const leg of route.legs) {
    if (leg.mode === 'bus' && leg.line_name && !names.includes(leg.line_name)) names.push(leg.line_name);
  }
  return names;
}

export default function FavoritesScreen() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const tabBarHeight = useBottomTabBarHeight();
  const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [selected, setSelected] = useState<SavedTrip | null>(null);
  const [userLoc, setUserLoc] = useState<{ lon: number; lat: number } | null>(null);
  const [legNames, setLegNames] = useState<Record<number, { board: string; alight: string }>>({});

  const stepsRef = useRef<BottomSheet>(null);
  const stepsSnapPoints = useMemo(() => ['30%', '70%'], []);

  useFocusEffect(useCallback(() => { setTrips(getTodayTrips()); }, []));

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: !selected });
  }, [navigation, selected]);

  useEffect(() => { getCurrentLocation().then(setUserLoc); }, []);

  const handleDelete = (trip: SavedTrip) => {
    Alert.alert('Eliminar ruta', `¿Eliminar "${trip.originName} → ${trip.destName}"?`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => { deleteTrip(trip.id); setTrips(getTodayTrips()); } },
    ]);
  };

  const selectTrip = useCallback(async (trip: SavedTrip) => {
    setSelected(trip);
    setLegNames({});
    stepsRef.current?.snapToIndex(0);
    const route = parseRouteJson(trip);
    const names: Record<number, { board: string; alight: string }> = {};
    for (let i = 0; i < route.legs.length; i++) {
      const leg = route.legs[i];
      if (leg.mode === 'bus' && leg.geometry.length >= 2) {
        const [board, alight] = await Promise.all([
          reverseGeocode(leg.geometry[0][0], leg.geometry[0][1]),
          reverseGeocode(leg.geometry[leg.geometry.length - 1][0], leg.geometry[leg.geometry.length - 1][1]),
        ]);
        names[i] = { board, alight };
        setLegNames({ ...names });
      }
    }
  }, []);

  // ================================================================
  // DETAIL VIEW
  // ================================================================
  if (selected) {
    const route = parseRouteJson(selected);
    const mapLegs: Leg[] = route.legs.map(l => ({ mode: l.mode, geometry: l.geometry, line_name: l.line_name ?? undefined }));

    return (
      <View className="flex-1">
        <RouteMap legs={mapLegs} currentLocation={userLoc} style={{ flex: 1 }} />
        <Pressable className="absolute left-4 rounded-full bg-white p-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={() => setSelected(null)}>
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>
        <View className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg" style={{ top: insets.top + 60 }}>
          <Text className="text-base font-bold text-[#09A6F3]">{formatDuration(route.total_duration_s)} · {formatDistance(route.total_distance_m)}</Text>
          <Text className="text-xs text-gray-400">{selected.originName} → {selected.destName}</Text>
        </View>
        <BottomSheet ref={stepsRef} index={0} snapPoints={stepsSnapPoints} backgroundStyle={{ borderRadius: 24 }} handleIndicatorStyle={{ backgroundColor: '#D1D5DB', width: 40 }}>
          <BottomSheetScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 32 }}>
            {route.legs.map((leg, index) => {
              const isLast = index === route.legs.length - 1;
              if (leg.mode === 'walk') return (
                <View key={`w-${index}`} className="flex-row">
                  <View className="mr-4 w-8 items-center">
                    <View className="h-8 w-8 items-center justify-center rounded-full bg-gray-200"><Feather name="navigation" size={14} color="#6B7280" /></View>
                    {!isLast && <View className="w-0.5 flex-1 bg-gray-200" />}
                  </View>
                  <View className="flex-1 pb-5">
                    <Text className="text-base font-semibold text-gray-800">Caminar</Text>
                    <Text className="text-sm text-gray-400">{formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}</Text>
                  </View>
                </View>
              );
              const names = legNames[index];
              return (
                <View key={`b-${index}`}>
                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-[#DDF6FF]"><Feather name="log-in" size={14} color={BLUE} /></View><View className="w-0.5 flex-1 bg-[#09A6F3]" /></View>
                    <View className="flex-1 pb-2"><Text className="text-base font-semibold text-[#09A6F3]">Tomar Línea {leg.line_name ?? '?'}</Text><Text className="text-sm text-gray-500">{names ? `en ${names.board}` : 'Cargando...'}</Text></View>
                  </View>
                  <View className="flex-row"><View className="mr-4 w-8 items-center"><View className="w-0.5 flex-1 bg-[#09A6F3]" /></View><View className="flex-1 py-1 pb-2"><Text className="text-xs text-gray-400">{formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}</Text></View></View>
                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-[#DDF6FF]"><Feather name="log-out" size={14} color={BLUE} /></View>{!isLast && <View className="w-0.5 flex-1 bg-gray-200" />}</View>
                    <View className="flex-1 pb-5"><Text className="text-base font-semibold text-gray-800">Bajar</Text><Text className="text-sm text-gray-500">{names ? `en ${names.alight}` : 'Cargando...'}</Text></View>
                  </View>
                </View>
              );
            })}
            <View className="flex-row">
              <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-red-100"><Feather name="map-pin" size={14} color="#EF4444" /></View></View>
              <View className="flex-1"><Text className="text-base font-semibold text-gray-800">Llegaste</Text><Text className="text-sm text-gray-400">{selected.destName}</Text></View>
            </View>
          </BottomSheetScrollView>
        </BottomSheet>
      </View>
    );
  }

  // ================================================================
  // LIST VIEW
  // ================================================================
  const commutes = trips.filter(t => t.type === 'commute');
  const oneTime = trips.filter(t => t.type === 'one_time');

  return (
      <View className="flex-1 bg-white">
        <ScrollView accessible={false} className="flex-1 px-5 pt-6" contentContainerStyle={{ paddingBottom: tabBarHeight + 12 }}>
          {trips.length === 0 ? (
            <View className="items-center gap-3 py-20">
              <Feather name="bookmark" size={48} color="#D1D5DB" />
              <Text className="text-center text-base text-gray-400" testID="favorites-empty">No tienes rutas guardadas.</Text>
              <Text className="text-center text-sm text-gray-400">Busca una ruta y toca "Guardar" para verla aquí.</Text>
            </View>
          ) : (
            <>
              {commutes.length > 0 && (
                <>
                  <Text className="mb-3 text-lg font-semibold text-gray-800" testID="favorites-commute-title">Recurrentes</Text>
                  {commutes.map((trip, idx) => <TripCard key={trip.id} trip={trip} index={idx} onPress={selectTrip} onDelete={handleDelete} />)}
                </>
              )}
              {oneTime.length > 0 && (
                <>
                  <Text className="mb-3 mt-4 text-lg font-semibold text-gray-800" testID="favorites-today-title">Para hoy</Text>
                  {oneTime.map((trip, idx) => <TripCard key={trip.id} trip={trip} index={idx} onPress={selectTrip} onDelete={handleDelete} />)}
                </>
              )}
            </>
          )}
        </ScrollView>
      </View>
  );
}

function TripCard({ trip, index, onPress, onDelete }: { trip: SavedTrip; index: number; onPress: (t: SavedTrip) => void; onDelete: (t: SavedTrip) => void }) {
  const route = parseRouteJson(trip);
  const lines = busLines(route);

  return (
    <Pressable testID={`favorites-trip-card-${index}`} className="mb-3 rounded-2xl border border-gray-200 bg-white p-4 active:bg-gray-50" onPress={() => onPress(trip)}>
      <View className="mb-2 flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-base font-semibold text-gray-800" numberOfLines={1}>{trip.originName}</Text>
          <Text className="text-sm text-gray-500" numberOfLines={1}>→ {trip.destName}</Text>
        </View>
        <Pressable testID={`favorites-delete-${index}`} className="ml-2 p-1" onPress={() => onDelete(trip)}>
          <Feather name="trash-2" size={16} color="#9CA3AF" />
        </Pressable>
      </View>
      <View className="mb-2 flex-row items-center gap-3">
        <Text className="text-lg font-bold text-gray-800">{formatDuration(route.total_duration_s)}</Text>
        <Text className="text-sm text-gray-400">{formatDistance(route.total_distance_m)}</Text>
        {route.total_fare_bob != null && (
          <Text className="text-sm font-semibold text-[#09A6F3]" testID={`favorites-fare-${index}`}>
            Bs. {route.total_fare_bob.toFixed(2)}
          </Text>
        )}
        {trip.departureTime && (
          <View className="ml-auto flex-row items-center gap-1 rounded-lg bg-[#DDF6FF] px-2 py-0.5" testID={`favorites-departure-${index}`}>
            <Feather name="clock" size={11} color={BLUE} />
            <Text className="text-xs font-semibold text-[#09A6F3]">{trip.departureTime}</Text>
          </View>
        )}
      </View>
      <View className="mb-2 flex-row items-center gap-1">
        {route.legs.map((leg, i) => <View key={i} className={`h-1.5 rounded-full ${leg.mode === 'bus' ? 'bg-[#09A6F3]' : 'bg-gray-300'}`} style={{ flex: leg.distance_m, minWidth: 6 }} />)}
      </View>
      <View className="flex-row flex-wrap items-center gap-2">
        {lines.map(name => <View key={name} className="flex-row items-center rounded-lg bg-[#DDF6FF] px-2 py-0.5"><Feather name="truck" size={11} color={BLUE} /><Text className="ml-1 text-xs font-semibold text-[#09A6F3]">{name}</Text></View>)}
        <View className={`rounded-lg px-2 py-0.5 ${trip.type === 'commute' ? 'bg-green-50' : 'bg-amber-50'}`}>
          <Text className={`text-xs font-medium ${trip.type === 'commute' ? 'text-green-600' : 'text-amber-600'}`}>{trip.type === 'commute' ? 'Recurrente' : 'Solo hoy'}</Text>
        </View>
      </View>
    </Pressable>
  );
}
