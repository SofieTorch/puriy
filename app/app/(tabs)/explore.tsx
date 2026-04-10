import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import Feather from '@expo/vector-icons/Feather';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  FlatList,
  Keyboard,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import Header from '@/components/header';
import PreferencesSheet from '@/components/preferences-sheet';
import RouteMap, { Leg } from '@/components/route-map';
import api, { DirectionsResponse } from '@/services/api';
import { GeocodingResult, searchAddress } from '@/services/geocoding';
import { includePendingLines, includePendingRoutes } from '@/services/preferences';

const BLUE = '#09A6F3';
const { height: SCREEN_HEIGHT } = Dimensions.get('window');

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const mins = Math.round(seconds / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

type ActiveField = 'origin' | 'destination' | null;

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
  const [directions, setDirections] = useState<DirectionsResponse | null>(null);

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
        const results = await searchAddress(queryText);
        setSuggestions(results);
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
    setDirections(null);
    setActiveField('origin');
  };

  const handleDestChange = (text: string) => {
    setDestText(text);
    setDestCoords(null);
    setDirections(null);
    setActiveField('destination');
  };

  const handleSearch = useCallback(async () => {
    if (!originCoords || !destCoords) return;

    Keyboard.dismiss();
    setLoading(true);
    setDirections(null);
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
      setDirections(result);
      stepsRef.current?.snapToIndex(0);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error desconocido';
      Alert.alert('Error', `No se pudo obtener direcciones: ${message}`);
    } finally {
      setLoading(false);
    }
  }, [originCoords, destCoords]);

  const handleBack = () => {
    setDirections(null);
    stepsRef.current?.close();
  };

  const mapLegs: Leg[] = directions
    ? directions.legs.map((leg) => ({
        mode: leg.mode,
        geometry: leg.geometry,
        line_name: leg.line_name ?? undefined,
      }))
    : [];

  // ---------- Results view (full-screen map + bottom sheet) ----------
  if (directions) {
    return (
      <View className="flex-1">
        <RouteMap legs={mapLegs} style={{ flex: 1 }} />

        {/* Back button floating over the map */}
        <Pressable
          className="absolute left-4 rounded-full bg-white p-3 shadow-lg"
          style={{ top: insets.top + 8 }}
          onPress={handleBack}
        >
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>

        {/* Summary pill floating over the map */}
        <View
          className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg"
          style={{ top: insets.top + 60 }}
        >
          <Text className="text-base font-bold text-[#09A6F3]">
            {formatDuration(directions.total_duration_s)} · {formatDistance(directions.total_distance_m)}
          </Text>
          <Text className="text-xs text-gray-400">
            {originText} → {destText}
          </Text>
        </View>

        {/* Steps bottom sheet */}
        <BottomSheet
          ref={stepsRef}
          index={0}
          snapPoints={stepsSnapPoints}
          backgroundStyle={{ borderRadius: 24 }}
          handleIndicatorStyle={{ backgroundColor: '#D1D5DB', width: 40 }}
        >
          <BottomSheetScrollView contentContainerStyle={{ padding: 20, gap: 12 }}>
            {directions.legs.map((leg, index) => (
              <View
                key={index}
                className="flex-row items-center rounded-2xl bg-[#F3F4F6] px-4 py-4"
              >
                <View
                  className={`mr-3 h-10 w-10 items-center justify-center rounded-full ${leg.mode === 'bus' ? 'bg-[#DDF6FF]' : 'bg-gray-200'}`}
                >
                  <Text className="text-lg">
                    {leg.mode === 'walk' ? '\u{1F6B6}' : '\u{1F68C}'}
                  </Text>
                </View>
                <View className="flex-1">
                  <Text className="text-base font-semibold text-gray-800">
                    {leg.mode === 'walk'
                      ? `Caminar ${formatDistance(leg.distance_m)}`
                      : `Línea ${leg.line_name ?? 'Desconocida'}`}
                  </Text>
                  <Text className="text-sm text-gray-500">
                    {leg.mode === 'bus' ? `${formatDistance(leg.distance_m)} · ` : ''}
                    {formatDuration(leg.duration_s)}
                  </Text>
                </View>
                <Feather
                  name={leg.mode === 'walk' ? 'navigation' : 'truck'}
                  size={16}
                  color="#9CA3AF"
                />
              </View>
            ))}
          </BottomSheetScrollView>
        </BottomSheet>
      </View>
    );
  }

  // ---------- Search view ----------
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

          <View className="mb-3">
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
