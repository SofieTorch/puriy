import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import Feather from '@expo/vector-icons/Feather';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Keyboard,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import Header from '@/components/header';
import PreferencesSheet from '@/components/preferences-sheet';
import RouteMap, { Leg } from '@/components/route-map';
import api, { DirectionsLeg, DirectionsResponse } from '@/services/api';
import { GeocodingResult, reverseGeocode, searchAddress } from '@/services/geocoding';
import { includePendingLines, includePendingRoutes } from '@/services/preferences';

const BLUE = '#09A6F3';

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const mins = Math.round(seconds / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

function routeSummary(legs: DirectionsLeg[]): { busLines: string[]; transfers: number; walkMin: number } {
  const busLines: string[] = [];
  let walkSeconds = 0;
  for (const leg of legs) {
    if (leg.mode === 'bus' && leg.line_name && !busLines.includes(leg.line_name)) {
      busLines.push(leg.line_name);
    }
    if (leg.mode === 'walk') walkSeconds += leg.duration_s;
  }
  return {
    busLines,
    transfers: Math.max(0, busLines.length - 1),
    walkMin: Math.round(walkSeconds / 60),
  };
}

type ActiveField = 'origin' | 'destination' | null;
type ViewState = 'search' | 'results' | 'detail';

export default function ExploreScreen() {
  const insets = useSafeAreaInsets();
  const [originText, setOriginText] = useState('');
  const [destText, setDestText] = useState('');
  const [originCoords, setOriginCoords] = useState<[number, number] | null>(null);
  const [destCoords, setDestCoords] = useState<[number, number] | null>(null);

  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [suggestions, setSuggestions] = useState<GeocodingResult[]>([]);
  const [searching, setSearching] = useState(false);

  const [loading, setLoading] = useState(false);
  const [routes, setRoutes] = useState<DirectionsResponse[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<DirectionsResponse | null>(null);
  const [view, setView] = useState<ViewState>('search');

  const [legNames, setLegNames] = useState<Record<number, { board: string; alight: string }>>({});

  const prefsRef = useRef<BottomSheet>(null);
  const stepsRef = useRef<BottomSheet>(null);
  const stepsSnapPoints = useMemo(() => ['30%', '70%'], []);

  const canSearch = originCoords !== null && destCoords !== null;

  // Debounced address search
  const queryText =
    activeField === 'origin' ? originText : activeField === 'destination' ? destText : '';

  useEffect(() => {
    if (!activeField || queryText.length < 3) {
      setSuggestions([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timeout = setTimeout(async () => {
      try {
        setSuggestions(await searchAddress(queryText));
      } catch {
        setSuggestions([]);
      }
      setSearching(false);
    }, 400);
    return () => clearTimeout(timeout);
  }, [queryText, activeField]);

  const pickSuggestion = useCallback(
    (result: GeocodingResult) => {
      if (activeField === 'origin') {
        setOriginText(result.shortName);
        setOriginCoords([result.lon, result.lat]);
      } else {
        setDestText(result.shortName);
        setDestCoords([result.lon, result.lat]);
      }
      setSuggestions([]);
      setActiveField(null);
      Keyboard.dismiss();
    },
    [activeField]
  );

  const handleOriginChange = (text: string) => {
    setOriginText(text);
    setOriginCoords(null);
    setRoutes([]);
    setView('search');
    setActiveField('origin');
  };

  const handleDestChange = (text: string) => {
    setDestText(text);
    setDestCoords(null);
    setRoutes([]);
    setView('search');
    setActiveField('destination');
  };

  // Search → show results list
  const handleSearch = useCallback(async () => {
    if (!originCoords || !destCoords) return;
    Keyboard.dismiss();
    setLoading(true);
    setRoutes([]);
    setSuggestions([]);
    setActiveField(null);

    try {
      const pendLines = includePendingLines();
      const pendRoutes = includePendingRoutes();
      const result = await api.getDirections(originCoords, destCoords, pendLines, pendRoutes);
      if (result.legs.length === 0) {
        Alert.alert('Sin resultados', 'No se encontró una ruta entre los puntos indicados.');
        return;
      }
      // For now we get one route; wrap in array for future multi-route support
      setRoutes([result]);
      setView('results');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error desconocido';
      Alert.alert('Error', `No se pudo obtener direcciones: ${message}`);
    } finally {
      setLoading(false);
    }
  }, [originCoords, destCoords]);

  // Select a route → show detail map + resolve street names
  const selectRoute = useCallback(async (route: DirectionsResponse) => {
    setSelectedRoute(route);
    setLegNames({});
    setView('detail');
    stepsRef.current?.snapToIndex(0);

    const names: Record<number, { board: string; alight: string }> = {};
    for (let i = 0; i < route.legs.length; i++) {
      const leg = route.legs[i];
      if (leg.mode === 'bus' && leg.geometry.length >= 2) {
        const start = leg.geometry[0];
        const end = leg.geometry[leg.geometry.length - 1];
        const [board, alight] = await Promise.all([
          reverseGeocode(start[0], start[1]),
          reverseGeocode(end[0], end[1]),
        ]);
        names[i] = { board, alight };
        setLegNames({ ...names });
      }
    }
  }, []);

  const mapLegs: Leg[] = selectedRoute
    ? selectedRoute.legs.map((leg) => ({
        mode: leg.mode,
        geometry: leg.geometry,
        line_name: leg.line_name ?? undefined,
      }))
    : [];

  // ====================================================================
  // VIEW: Detail (full-screen map + steps bottom sheet)
  // ====================================================================
  if (view === 'detail' && selectedRoute) {
    return (
      <View className="flex-1">
        <RouteMap legs={mapLegs} style={{ flex: 1 }} />

        <Pressable
          className="absolute left-4 rounded-full bg-white p-3 shadow-lg"
          style={{ top: insets.top + 8 }}
          onPress={() => setView('results')}
        >
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>

        <View
          className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg"
          style={{ top: insets.top + 60 }}
        >
          <Text className="text-base font-bold text-[#09A6F3]">
            {formatDuration(selectedRoute.total_duration_s)} ·{' '}
            {formatDistance(selectedRoute.total_distance_m)}
          </Text>
          <Text className="text-xs text-gray-400">
            {originText} → {destText}
          </Text>
        </View>

        <BottomSheet
          ref={stepsRef}
          index={0}
          snapPoints={stepsSnapPoints}
          backgroundStyle={{ borderRadius: 24 }}
          handleIndicatorStyle={{ backgroundColor: '#D1D5DB', width: 40 }}
        >
          <BottomSheetScrollView
            contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 32 }}
          >
            {selectedRoute.legs.map((leg, index) => {
              const isLast = index === selectedRoute.legs.length - 1;

              if (leg.mode === 'walk') {
                return (
                  <View key={`w-${index}`} className="flex-row">
                    <View className="mr-4 w-8 items-center">
                      <View className="h-8 w-8 items-center justify-center rounded-full bg-gray-200">
                        <Feather name="navigation" size={14} color="#6B7280" />
                      </View>
                      {!isLast && <View className="w-0.5 flex-1 bg-gray-200" />}
                    </View>
                    <View className="flex-1 pb-5">
                      <Text className="text-base font-semibold text-gray-800">Caminar</Text>
                      <Text className="text-sm text-gray-400">
                        {formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}
                      </Text>
                    </View>
                  </View>
                );
              }

              const names = legNames[index];
              return (
                <View key={`b-${index}`}>
                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center">
                      <View className="h-8 w-8 items-center justify-center rounded-full bg-[#DDF6FF]">
                        <Feather name="log-in" size={14} color={BLUE} />
                      </View>
                      <View className="w-0.5 flex-1 bg-[#09A6F3]" />
                    </View>
                    <View className="flex-1 pb-2">
                      <Text className="text-base font-semibold text-[#09A6F3]">
                        Tomar Línea {leg.line_name ?? '?'}
                      </Text>
                      <Text className="text-sm text-gray-500">
                        {names ? `en ${names.board}` : 'Cargando ubicación...'}
                      </Text>
                    </View>
                  </View>

                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center">
                      <View className="w-0.5 flex-1 bg-[#09A6F3]" />
                    </View>
                    <View className="flex-1 py-1 pb-2">
                      <Text className="text-xs text-gray-400">
                        {formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}
                      </Text>
                    </View>
                  </View>

                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center">
                      <View className="h-8 w-8 items-center justify-center rounded-full bg-[#DDF6FF]">
                        <Feather name="log-out" size={14} color={BLUE} />
                      </View>
                      {!isLast && <View className="w-0.5 flex-1 bg-gray-200" />}
                    </View>
                    <View className="flex-1 pb-5">
                      <Text className="text-base font-semibold text-gray-800">Bajar</Text>
                      <Text className="text-sm text-gray-500">
                        {names ? `en ${names.alight}` : 'Cargando ubicación...'}
                      </Text>
                    </View>
                  </View>
                </View>
              );
            })}

            <View className="flex-row">
              <View className="mr-4 w-8 items-center">
                <View className="h-8 w-8 items-center justify-center rounded-full bg-red-100">
                  <Feather name="map-pin" size={14} color="#EF4444" />
                </View>
              </View>
              <View className="flex-1">
                <Text className="text-base font-semibold text-gray-800">Llegaste</Text>
                <Text className="text-sm text-gray-400">{destText}</Text>
              </View>
            </View>
          </BottomSheetScrollView>
        </BottomSheet>
      </View>
    );
  }

  // ====================================================================
  // VIEW: Results list (route options)
  // ====================================================================
  if (view === 'results' && routes.length > 0) {
    return (
      <SafeAreaView className="flex-1 bg-[#09A6F3]">
        <View className="flex-1 bg-white">
          <Header title="Explorar" />

          <View className="px-5 pt-4">
            <View className="mb-2 flex-row items-center gap-2">
              <Pressable className="p-1" onPress={() => setView('search')}>
                <Feather name="arrow-left" size={22} color="#333" />
              </Pressable>
              <View className="flex-1">
                <View className="h-11 flex-row items-center rounded-lg border border-gray-200 bg-gray-50 px-3">
                  <Feather name="crosshair" size={16} color={BLUE} />
                  <TextInput
                    className="ml-2 flex-1 text-sm"
                    placeholder="Punto de partida"
                    value={originText}
                    onChangeText={handleOriginChange}
                    onFocus={() => setActiveField('origin')}
                  />
                  {originCoords && <Feather name="check-circle" size={14} color="#22C55E" />}
                </View>
              </View>
              <Pressable
                className="items-center justify-center p-1"
                onPress={() => {
                  setOriginText(destText);
                  setDestText(originText);
                  setOriginCoords(destCoords);
                  setDestCoords(originCoords);
                  setRoutes([]);
                }}
              >
                <Feather name="repeat" size={16} color={BLUE} />
              </Pressable>
            </View>
            <View className="mb-2 flex-row items-center gap-2">
              <View className="w-8" />
              <View className="flex-1">
                <View className="h-11 flex-row items-center rounded-lg border border-gray-200 bg-gray-50 px-3">
                  <Feather name="target" size={16} color={BLUE} />
                  <TextInput
                    className="ml-2 flex-1 text-sm"
                    placeholder="Destino"
                    value={destText}
                    onChangeText={handleDestChange}
                    onFocus={() => setActiveField('destination')}
                  />
                  {destCoords && <Feather name="check-circle" size={14} color="#22C55E" />}
                </View>
              </View>
              <Pressable
                className="items-center justify-center rounded-lg bg-[#09A6F3] p-2"
                onPress={handleSearch}
                disabled={!canSearch || loading}
              >
                {loading ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Feather name="search" size={16} color="#fff" />
                )}
              </Pressable>
            </View>

            {activeField && suggestions.length > 0 && (
              <View className="mb-2 rounded-xl border border-gray-200 bg-white">
                <FlatList
                  data={suggestions}
                  keyExtractor={(_, i) => String(i)}
                  keyboardShouldPersistTaps="handled"
                  scrollEnabled={false}
                  renderItem={({ item }) => (
                    <Pressable
                      className="border-b border-gray-100 px-4 py-3"
                      onPress={() => pickSuggestion(item)}
                    >
                      <Text className="text-sm font-medium text-gray-800" numberOfLines={1}>
                        {item.shortName}
                      </Text>
                      <Text className="text-xs text-gray-400" numberOfLines={1}>
                        {item.displayName}
                      </Text>
                    </Pressable>
                  )}
                />
              </View>
            )}

            {activeField && searching && (
              <View className="mb-2 items-center py-1">
                <ActivityIndicator size="small" color={BLUE} />
              </View>
            )}
          </View>

          <ScrollView className="flex-1 px-5">
            <Text className="mb-3 text-lg font-semibold text-gray-800">
              Rutas disponibles
            </Text>

            {routes.map((route, idx) => {
              const summary = routeSummary(route.legs);
              return (
                <Pressable
                  key={idx}
                  className="mb-3 rounded-2xl border border-gray-200 bg-white p-4 active:bg-gray-50"
                  onPress={() => selectRoute(route)}
                >
                  {/* Time and distance */}
                  <View className="mb-2 flex-row items-center justify-between">
                    <Text className="text-xl font-bold text-gray-800">
                      {formatDuration(route.total_duration_s)}
                    </Text>
                    <Text className="text-sm text-gray-400">
                      {formatDistance(route.total_distance_m)}
                    </Text>
                  </View>

                  {/* Visual leg strip */}
                  <View className="mb-3 flex-row items-center gap-1">
                    {route.legs.map((leg, i) => (
                      <View
                        key={i}
                        className={`h-2 rounded-full ${leg.mode === 'bus' ? 'bg-[#09A6F3]' : 'bg-gray-300'}`}
                        style={{
                          flex: leg.distance_m,
                          minWidth: 8,
                        }}
                      />
                    ))}
                  </View>

                  {/* Bus lines and info */}
                  <View className="flex-row flex-wrap items-center gap-2">
                    {summary.busLines.map((name) => (
                      <View key={name} className="flex-row items-center rounded-lg bg-[#DDF6FF] px-2.5 py-1">
                        <Feather name="truck" size={12} color={BLUE} />
                        <Text className="ml-1 text-sm font-semibold text-[#09A6F3]">{name}</Text>
                      </View>
                    ))}
                    {summary.transfers > 0 && (
                      <Text className="text-xs text-gray-400">
                        {summary.transfers} transbordo{summary.transfers > 1 ? 's' : ''}
                      </Text>
                    )}
                    {summary.walkMin > 0 && (
                      <Text className="text-xs text-gray-400">
                        🚶 {summary.walkMin} min caminando
                      </Text>
                    )}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
      </SafeAreaView>
    );
  }

  // ====================================================================
  // VIEW: Search
  // ====================================================================
  return (
    <SafeAreaView className="flex-1 bg-[#09A6F3]">
      <View className="flex-1 bg-white">
        <Header title="Explorar" />

        <View className="flex-1 px-5 pt-6">
          <View className="mb-4 flex-row justify-end">
            <Pressable
              className="h-11 w-11 items-center justify-center rounded-xl bg-[#DDF6FF]"
              onPress={() => prefsRef.current?.expand()}
            >
              <Feather name="settings" size={20} color={BLUE} />
            </Pressable>
          </View>

          <View className="mb-3 flex-row items-center gap-2">
            <View className="flex-1">
              <View className="h-14 flex-row items-center rounded-xl border-2 border-[#09A6F3] bg-white px-3">
                <Feather name="crosshair" size={22} color={BLUE} />
                <TextInput
                  className="ml-2 flex-1 text-base"
                  placeholder="Punto de partida"
                  placeholderTextColor={BLUE}
                  value={originText}
                  onChangeText={handleOriginChange}
                  onFocus={() => setActiveField('origin')}
                />
                {originCoords && <Feather name="check-circle" size={18} color="#22C55E" />}
              </View>
            </View>
            <Pressable
              className="h-14 w-10 items-center justify-center"
              onPress={() => {
                setOriginText(destText);
                setDestText(originText);
                setOriginCoords(destCoords);
                setDestCoords(originCoords);
                setRoutes([]);
                setView('search');
              }}
            >
              <Feather name="repeat" size={18} color={BLUE} />
            </Pressable>
          </View>

          <View className="mb-3">
            <View className="h-14 flex-row items-center rounded-xl border-2 border-[#09A6F3] bg-white px-3">
              <Feather name="target" size={22} color={BLUE} />
              <TextInput
                className="ml-2 flex-1 text-base"
                placeholder="Destino"
                placeholderTextColor={BLUE}
                value={destText}
                onChangeText={handleDestChange}
                onFocus={() => setActiveField('destination')}
              />
              {destCoords && <Feather name="check-circle" size={18} color="#22C55E" />}
            </View>
          </View>

          {activeField && suggestions.length > 0 && (
            <View className="mb-3 rounded-xl border border-gray-200 bg-white">
              <FlatList
                data={suggestions}
                keyExtractor={(_, i) => String(i)}
                keyboardShouldPersistTaps="handled"
                scrollEnabled={false}
                renderItem={({ item }) => (
                  <Pressable
                    className="border-b border-gray-100 px-4 py-3"
                    onPress={() => pickSuggestion(item)}
                  >
                    <Text className="text-sm font-medium text-gray-800" numberOfLines={1}>
                      {item.shortName}
                    </Text>
                    <Text className="text-xs text-gray-400" numberOfLines={1}>
                      {item.displayName}
                    </Text>
                  </Pressable>
                )}
              />
            </View>
          )}

          {activeField && searching && (
            <View className="mb-3 items-center py-2">
              <ActivityIndicator size="small" color={BLUE} />
            </View>
          )}

          <Pressable
            className={`mb-5 h-14 items-center justify-center rounded-xl ${canSearch ? 'bg-[#09A6F3]' : 'bg-[#B0E2FA]'}`}
            onPress={handleSearch}
            disabled={!canSearch || loading}
          >
            {loading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text className="text-lg font-bold text-white">Buscar ruta</Text>
            )}
          </Pressable>
        </View>
      </View>

      <PreferencesSheet ref={prefsRef} />
    </SafeAreaView>
  );
}
