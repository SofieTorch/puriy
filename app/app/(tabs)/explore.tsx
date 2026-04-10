import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import Feather from '@expo/vector-icons/Feather';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
import RouteMap, { Leg, LineRoute } from '@/components/route-map';
import api, { DirectionsLeg, DirectionsResponse, NearbyLineWithRoute } from '@/services/api';
import { getCurrentLocation, watchLocation } from '@/services/current-location';
import { GeocodingResult, reverseGeocode, searchAddress } from '@/services/geocoding';
import { includePendingLines, includePendingRoutes } from '@/services/preferences';
import { saveTrip, TripType } from '@/services/saved-trips';
import { addToHistory, filterHistory } from '@/services/search-history';
import { SearchHistoryEntry } from '@/db/schema';

const BLUE = '#09A6F3';

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function formatDuration(s: number): string {
  const mins = Math.round(s / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

function routeSummary(legs: DirectionsLeg[]) {
  const busLines: string[] = [];
  let walkSec = 0;
  for (const leg of legs) {
    if (leg.mode === 'bus' && leg.line_name && !busLines.includes(leg.line_name)) busLines.push(leg.line_name);
    if (leg.mode === 'walk') walkSec += leg.duration_s;
  }
  return { busLines, transfers: Math.max(0, busLines.length - 1), walkMin: Math.round(walkSec / 60) };
}

type ActiveField = 'origin' | 'destination' | null;
type ViewState = 'search' | 'results' | 'detail' | 'line_detail';

export default function ExploreScreen() {
  const insets = useSafeAreaInsets();

  // Location
  const [userLoc, setUserLoc] = useState<{ lon: number; lat: number } | null>(null);
  const [usingCurrentLoc, setUsingCurrentLoc] = useState(true);

  // Search inputs
  const [originText, setOriginText] = useState('Ubicación actual');
  const [destText, setDestText] = useState('');
  const [originCoords, setOriginCoords] = useState<[number, number] | null>(null);
  const [destCoords, setDestCoords] = useState<[number, number] | null>(null);

  // Autocomplete
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [suggestions, setSuggestions] = useState<GeocodingResult[]>([]);
  const [historyItems, setHistoryItems] = useState<SearchHistoryEntry[]>([]);
  const [searching, setSearching] = useState(false);

  // Route results
  const [loading, setLoading] = useState(false);
  const [routes, setRoutes] = useState<DirectionsResponse[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<DirectionsResponse | null>(null);
  const [legNames, setLegNames] = useState<Record<number, { board: string; alight: string }>>({});

  // Nearby lines
  const [nearbyLines, setNearbyLines] = useState<NearbyLineWithRoute[]>([]);
  const [selectedLine, setSelectedLine] = useState<NearbyLineWithRoute | null>(null);
  const [nearbyRadius, setNearbyRadius] = useState(2000);
  const [radiusExpanded, setRadiusExpanded] = useState(false);

  // View state
  const [view, setView] = useState<ViewState>('search');

  const prefsRef = useRef<BottomSheet>(null);
  const stepsRef = useRef<BottomSheet>(null);
  const stepsSnapPoints = useMemo(() => ['30%', '70%'], []);

  const canSearch = originCoords !== null && destCoords !== null;

  // Track location as primitive values to avoid object identity issues
  const [userLon, setUserLon] = useState<number | null>(null);
  const [userLat, setUserLat] = useState<number | null>(null);

  // Watch location for real-time updates
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    (async () => {
      const loc = await getCurrentLocation();
      if (loc) {
        setUserLoc(loc);
        setUserLon(loc.lon);
        setUserLat(loc.lat);
        if (usingCurrentLoc) setOriginCoords([loc.lon, loc.lat]);
      }

      unsubscribe = await watchLocation((newLoc) => {
        setUserLoc(newLoc);
        setUserLon(newLoc.lon);
        setUserLat(newLoc.lat);
        if (usingCurrentLoc) setOriginCoords([newLoc.lon, newLoc.lat]);
      });
    })();

    return () => { unsubscribe?.(); };
  }, [usingCurrentLoc]);

  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyError, setNearbyError] = useState<string | null>(null);
  const [hasPendingNearby, setHasPendingNearby] = useState(false);

  // Fetch nearby lines whenever location or radius changes
  useEffect(() => {
    if (userLon === null || userLat === null) return;
    let cancelled = false;
    const pending = includePendingLines() || includePendingRoutes();

    setNearbyLoading(true);
    setNearbyError(null);

    (async () => {
      try {
        // Fetch with user preferences
        const lines = await api.getNearbyLinesByLocation(userLon, userLat, nearbyRadius, pending);
        if (cancelled) return;
        setNearbyLines(lines);

        // If no results and preferences are off, check if there ARE pending lines nearby
        if (lines.length === 0 && !pending) {
          const withPending = await api.getNearbyLinesByLocation(userLon, userLat, nearbyRadius, true);
          if (!cancelled) setHasPendingNearby(withPending.length > 0);
        } else {
          setHasPendingNearby(false);
        }
      } catch (e) {
        if (!cancelled) {
          setNearbyError(e instanceof Error ? e.message : 'Error al buscar líneas');
          setNearbyLines([]);
        }
      } finally {
        if (!cancelled) setNearbyLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [userLon, userLat, nearbyRadius]);

  // Debounced search + history
  const queryText = activeField === 'origin' ? originText : activeField === 'destination' ? destText : '';

  useEffect(() => {
    if (!activeField) { setSuggestions([]); setHistoryItems([]); setSearching(false); return; }
    setHistoryItems(filterHistory(queryText));
    if (queryText.length < 3) { setSuggestions([]); setSearching(false); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const results = await searchAddress(queryText);
        const histNames = new Set(filterHistory(queryText).map(h => h.name.toLowerCase()));
        setSuggestions(results.filter(r => !histNames.has(r.shortName.toLowerCase())));
      } catch { setSuggestions([]); }
      setSearching(false);
    }, 400);
    return () => clearTimeout(t);
  }, [queryText, activeField]);

  const pickSuggestion = useCallback((result: GeocodingResult) => {
    addToHistory(result.shortName, result.lon, result.lat);
    if (activeField === 'origin') {
      setOriginText(result.shortName); setOriginCoords([result.lon, result.lat]); setUsingCurrentLoc(false);
    } else {
      setDestText(result.shortName); setDestCoords([result.lon, result.lat]);
    }
    setSuggestions([]); setHistoryItems([]); setActiveField(null); Keyboard.dismiss();
  }, [activeField]);

  const pickHistoryItem = useCallback((entry: SearchHistoryEntry) => {
    if (activeField === 'origin') {
      setOriginText(entry.name); setOriginCoords([entry.lon, entry.lat]); setUsingCurrentLoc(false);
    } else {
      setDestText(entry.name); setDestCoords([entry.lon, entry.lat]);
    }
    setSuggestions([]); setHistoryItems([]); setActiveField(null); Keyboard.dismiss();
  }, [activeField]);

  const handleOriginChange = (text: string) => {
    setOriginText(text); setOriginCoords(null); setUsingCurrentLoc(false);
    setRoutes([]); setView('search'); setActiveField('origin');
  };

  const handleDestChange = (text: string) => {
    setDestText(text); setDestCoords(null);
    setRoutes([]); setView('search'); setActiveField('destination');
  };

  const handleSearch = useCallback(async () => {
    if (!originCoords || !destCoords) return;
    Keyboard.dismiss(); setLoading(true); setRoutes([]); setSuggestions([]); setHistoryItems([]); setActiveField(null);
    try {
      const result = await api.getDirections(originCoords, destCoords, includePendingLines(), includePendingRoutes());
      if (result.legs.length === 0) { Alert.alert('Sin resultados', 'No se encontró una ruta.'); return; }
      setRoutes([result]); setView('results');
    } catch (e) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Error desconocido');
    } finally { setLoading(false); }
  }, [originCoords, destCoords]);

  const selectRoute = useCallback(async (route: DirectionsResponse) => {
    setSelectedRoute(route); setLegNames({}); setView('detail');
    stepsRef.current?.snapToIndex(0);
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

  const handleSaveTrip = useCallback((type: TripType) => {
    if (!selectedRoute || !originCoords || !destCoords) return;
    saveTrip({ originName: originText, destName: destText, originCoords, destCoords, type, route: selectedRoute });
    Alert.alert('Ruta guardada', type === 'commute' ? 'Se mostrará todos los días.' : 'Se mostrará solo por hoy.');
  }, [selectedRoute, originCoords, destCoords, originText, destText]);

  const promptSaveTrip = useCallback(() => {
    Alert.alert('Guardar ruta', '¿Cómo quieres guardar?', [
      { text: 'Solo por hoy', onPress: () => handleSaveTrip('one_time') },
      { text: 'Viaje recurrente', onPress: () => handleSaveTrip('commute') },
      { text: 'Cancelar', style: 'cancel' },
    ]);
  }, [handleSaveTrip]);

  const mapLegs: Leg[] = selectedRoute?.legs.map(l => ({ mode: l.mode, geometry: l.geometry, line_name: l.line_name ?? undefined })) ?? [];

  // Autocomplete dropdown (reused in search + results views)
  const autocompleteDropdown = activeField && (historyItems.length > 0 || suggestions.length > 0) ? (
    <View className="mb-3 rounded-xl border border-gray-200 bg-white">
      {historyItems.map(entry => (
        <Pressable key={`h-${entry.id}`} className="flex-row items-center border-b border-gray-100 px-4 py-3" onPress={() => pickHistoryItem(entry)}>
          <Feather name="clock" size={14} color="#9CA3AF" />
          <Text className="ml-2 flex-1 text-sm text-gray-700" numberOfLines={1}>{entry.name}</Text>
        </Pressable>
      ))}
      {suggestions.map((item, i) => (
        <Pressable key={`s-${i}`} className="border-b border-gray-100 px-4 py-3" onPress={() => pickSuggestion(item)}>
          <Text className="text-sm font-medium text-gray-800" numberOfLines={1}>{item.shortName}</Text>
          <Text className="text-xs text-gray-400" numberOfLines={1}>{item.displayName}</Text>
        </Pressable>
      ))}
      {searching && <View className="items-center py-3"><ActivityIndicator size="small" color={BLUE} /></View>}
    </View>
  ) : null;

  // ================================================================
  // LINE DETAIL VIEW
  // ================================================================
  if (view === 'line_detail' && selectedLine) {
    const lr: LineRoute | null = selectedLine.route_geojson
      ? { coordinates: selectedLine.route_geojson.coordinates, name: selectedLine.line_name }
      : null;
    return (
      <View className="flex-1">
        <RouteMap lineRoute={lr} currentLocation={userLoc} style={{ flex: 1 }} />
        <Pressable className="absolute left-4 rounded-full bg-white p-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={() => { setSelectedLine(null); setView('search'); }}>
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>
        <View className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg" style={{ top: insets.top + 60 }}>
          <Text className="text-base font-bold text-[#09A6F3]">Línea {selectedLine.line_name}</Text>
          {selectedLine.line_description && <Text className="text-xs text-gray-400">{selectedLine.line_description}</Text>}
        </View>
      </View>
    );
  }

  // ================================================================
  // ROUTE DETAIL VIEW
  // ================================================================
  if (view === 'detail' && selectedRoute) {
    return (
      <View className="flex-1">
        <RouteMap legs={mapLegs} currentLocation={userLoc} style={{ flex: 1 }} />
        <Pressable className="absolute left-4 rounded-full bg-white p-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={() => setView('results')}>
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>
        <Pressable className="absolute right-4 flex-row items-center rounded-full bg-white px-4 py-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={promptSaveTrip}>
          <Feather name="bookmark" size={18} color={BLUE} />
          <Text className="ml-2 text-sm font-semibold text-[#09A6F3]">Guardar</Text>
        </Pressable>
        <View className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg" style={{ top: insets.top + 60 }}>
          <Text className="text-base font-bold text-[#09A6F3]">{formatDuration(selectedRoute.total_duration_s)} · {formatDistance(selectedRoute.total_distance_m)}</Text>
          <Text className="text-xs text-gray-400">{originText} → {destText}</Text>
        </View>
        <BottomSheet ref={stepsRef} index={0} snapPoints={stepsSnapPoints} backgroundStyle={{ borderRadius: 24 }} handleIndicatorStyle={{ backgroundColor: '#D1D5DB', width: 40 }}>
          <BottomSheetScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 32 }}>
            {selectedRoute.legs.map((leg, index) => {
              const isLast = index === selectedRoute.legs.length - 1;
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
              <View className="flex-1"><Text className="text-base font-semibold text-gray-800">Llegaste</Text><Text className="text-sm text-gray-400">{destText}</Text></View>
            </View>
          </BottomSheetScrollView>
        </BottomSheet>
      </View>
    );
  }

  // ================================================================
  // RESULTS VIEW
  // ================================================================
  if (view === 'results' && routes.length > 0) {
    return (
      <SafeAreaView className="flex-1 bg-[#09A6F3]">
        <View className="flex-1 bg-white">
          <Header title="Explorar" />
          <View className="px-5 pt-4">
            <View className="mb-2 flex-row items-center gap-2">
              <Pressable className="p-1" onPress={() => setView('search')}><Feather name="arrow-left" size={22} color="#333" /></Pressable>
              <View className="flex-1">
                <View className="h-11 flex-row items-center rounded-lg border border-gray-200 bg-gray-50 px-3">
                  <Feather name="crosshair" size={16} color={BLUE} />
                  <TextInput className="ml-2 flex-1 text-sm" placeholder="Punto de partida" value={originText} onChangeText={handleOriginChange} onFocus={() => setActiveField('origin')} />
                  {originCoords && <Feather name="check-circle" size={14} color="#22C55E" />}
                </View>
              </View>
              <Pressable className="p-1" onPress={() => { setOriginText(destText); setDestText(originText); setOriginCoords(destCoords); setDestCoords(originCoords); setUsingCurrentLoc(false); setRoutes([]); }}>
                <Feather name="repeat" size={16} color={BLUE} />
              </Pressable>
            </View>
            <View className="mb-2 flex-row items-center gap-2">
              <View className="w-8" />
              <View className="flex-1">
                <View className="h-11 flex-row items-center rounded-lg border border-gray-200 bg-gray-50 px-3">
                  <Feather name="target" size={16} color={BLUE} />
                  <TextInput className="ml-2 flex-1 text-sm" placeholder="Destino" value={destText} onChangeText={handleDestChange} onFocus={() => setActiveField('destination')} />
                  {destCoords && <Feather name="check-circle" size={14} color="#22C55E" />}
                </View>
              </View>
              <Pressable className="rounded-lg bg-[#09A6F3] p-2" onPress={handleSearch} disabled={!canSearch || loading}>
                {loading ? <ActivityIndicator size="small" color="#fff" /> : <Feather name="search" size={16} color="#fff" />}
              </Pressable>
            </View>
            {autocompleteDropdown}
          </View>
          <ScrollView className="flex-1 px-5">
            <Text className="mb-3 text-lg font-semibold text-gray-800">Rutas disponibles</Text>
            {routes.map((route, idx) => {
              const s = routeSummary(route.legs);
              return (
                <Pressable key={idx} className="mb-3 rounded-2xl border border-gray-200 bg-white p-4 active:bg-gray-50" onPress={() => selectRoute(route)}>
                  <View className="mb-2 flex-row items-center justify-between">
                    <Text className="text-xl font-bold text-gray-800">{formatDuration(route.total_duration_s)}</Text>
                    <Text className="text-sm text-gray-400">{formatDistance(route.total_distance_m)}</Text>
                  </View>
                  <View className="mb-3 flex-row items-center gap-1">
                    {route.legs.map((leg, i) => <View key={i} className={`h-2 rounded-full ${leg.mode === 'bus' ? 'bg-[#09A6F3]' : 'bg-gray-300'}`} style={{ flex: leg.distance_m, minWidth: 8 }} />)}
                  </View>
                  <View className="flex-row flex-wrap items-center gap-2">
                    {s.busLines.map(name => <View key={name} className="flex-row items-center rounded-lg bg-[#DDF6FF] px-2.5 py-1"><Feather name="truck" size={12} color={BLUE} /><Text className="ml-1 text-sm font-semibold text-[#09A6F3]">{name}</Text></View>)}
                    {s.transfers > 0 && <Text className="text-xs text-gray-400">{s.transfers} transbordo{s.transfers > 1 ? 's' : ''}</Text>}
                    {s.walkMin > 0 && <Text className="text-xs text-gray-400">🚶 {s.walkMin} min</Text>}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
      </SafeAreaView>
    );
  }

  // ================================================================
  // SEARCH VIEW
  // ================================================================
  return (
    <SafeAreaView className="flex-1 bg-[#09A6F3]">
      <Pressable className="flex-1 bg-white" onPress={() => { Keyboard.dismiss(); setActiveField(null); }}>
        <Header title="Explorar" />
        <ScrollView
          className="flex-1 px-5 pt-6"
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
        >
          <View className="mb-4 flex-row justify-end">
            <Pressable className="h-11 w-11 items-center justify-center rounded-xl bg-[#DDF6FF]" onPress={() => prefsRef.current?.expand()}>
              <Feather name="settings" size={20} color={BLUE} />
            </Pressable>
          </View>

          <View className="mb-3 flex-row items-center gap-2">
            <View className="flex-1">
              <View className="h-14 flex-row items-center rounded-xl border-2 border-[#09A6F3] bg-white px-3">
                <Feather name={usingCurrentLoc ? 'navigation' : 'crosshair'} size={22} color={BLUE} />
                <TextInput
                  className="ml-2 flex-1 text-base"
                  placeholder="Punto de partida"
                  placeholderTextColor={BLUE}
                  value={originText}
                  onChangeText={handleOriginChange}
                  onFocus={() => setActiveField('origin')}
                />
                {originCoords && <Feather name={usingCurrentLoc ? 'navigation' : 'check-circle'} size={18} color="#22C55E" />}
              </View>
            </View>
            <Pressable className="h-14 w-10 items-center justify-center" onPress={() => { setOriginText(destText); setDestText(originText); setOriginCoords(destCoords); setDestCoords(originCoords); setUsingCurrentLoc(false); setRoutes([]); }}>
              <Feather name="repeat" size={18} color={BLUE} />
            </Pressable>
          </View>

          <View className="mb-3">
            <View className="h-14 flex-row items-center rounded-xl border-2 border-[#09A6F3] bg-white px-3">
              <Feather name="target" size={22} color={BLUE} />
              <TextInput className="ml-2 flex-1 text-base" placeholder="Destino" placeholderTextColor={BLUE} value={destText} onChangeText={handleDestChange} onFocus={() => setActiveField('destination')} />
              {destCoords && <Feather name="check-circle" size={18} color="#22C55E" />}
            </View>
          </View>

          {autocompleteDropdown}

          <Pressable
            className={`mb-5 h-14 items-center justify-center rounded-xl ${canSearch ? 'bg-[#09A6F3]' : 'bg-[#B0E2FA]'}`}
            onPress={handleSearch}
            disabled={!canSearch || loading}
          >
            {loading ? <ActivityIndicator color="#FFFFFF" /> : <Text className="text-lg font-bold text-white">Buscar ruta</Text>}
          </Pressable>

          {/* Nearby lines */}
          <View className="mb-6">
            <Pressable
              className="mb-3 flex-row items-center justify-between"
              onPress={() => setRadiusExpanded(!radiusExpanded)}
            >
              <Text className="text-lg font-semibold text-gray-800">Líneas cercanas</Text>
              <View className="flex-row items-center gap-1">
                <Text className="text-sm text-gray-400">{nearbyRadius >= 1000 ? `${(nearbyRadius / 1000).toFixed(1)} km` : `${nearbyRadius} m`}</Text>
                <Feather name={radiusExpanded ? 'chevron-up' : 'chevron-down'} size={16} color="#9CA3AF" />
              </View>
            </Pressable>

            {radiusExpanded && (
              <View className="mb-3 rounded-xl border border-gray-200 bg-gray-50 p-3">
                <Text className="mb-2 text-xs font-medium text-gray-500">Radio de búsqueda</Text>
                <View className="mb-2 flex-row gap-2">
                  {[500, 1000, 2000, 5000].map(r => (
                    <Pressable
                      key={r}
                      className={`flex-1 items-center rounded-lg py-2 ${nearbyRadius === r ? 'bg-[#09A6F3]' : 'bg-white border border-gray-200'}`}
                      onPress={() => setNearbyRadius(r)}
                    >
                      <Text className={`text-sm font-medium ${nearbyRadius === r ? 'text-white' : 'text-gray-600'}`}>
                        {r >= 1000 ? `${r / 1000}km` : `${r}m`}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            )}
            {!userLoc || nearbyLoading ? (
              <View className="items-center py-4">
                <ActivityIndicator size="small" color={BLUE} />
                <Text className="mt-2 text-sm text-gray-400">
                  {!userLoc ? 'Obteniendo ubicación...' : 'Buscando líneas...'}
                </Text>
              </View>
            ) : nearbyError ? (
              <View className="rounded-xl bg-red-50 px-4 py-3">
                <Text className="text-sm text-red-500">{nearbyError}</Text>
              </View>
            ) : nearbyLines.length === 0 ? (
              <View>
                <Text className="text-sm text-gray-400">No se encontraron líneas cerca de tu ubicación.</Text>
                {hasPendingNearby && (
                  <Pressable
                    className="mt-2 rounded-xl bg-amber-50 px-4 py-3"
                    onPress={() => prefsRef.current?.expand()}
                  >
                    <Text className="text-sm text-amber-700">
                      Hay líneas pendientes cerca. Toca aquí para activar "Incluir líneas pendientes" en preferencias.
                    </Text>
                  </Pressable>
                )}
              </View>
            ) : (
              nearbyLines.map(line => (
                <Pressable
                  key={line.line_id}
                  className="mb-2 flex-row items-center rounded-xl border border-gray-200 bg-white px-4 py-3 active:bg-gray-50"
                  onPress={() => { setSelectedLine(line); setView('line_detail'); }}
                >
                  <View className="mr-3 h-10 w-10 items-center justify-center rounded-full bg-[#DDF6FF]">
                    <Feather name="truck" size={18} color={BLUE} />
                  </View>
                  <View className="flex-1">
                    <Text className="text-base font-semibold text-gray-800">Línea {line.line_name}</Text>
                    {line.line_description && <Text className="text-sm text-gray-500" numberOfLines={1}>{line.line_description}</Text>}
                  </View>
                  <Feather name="chevron-right" size={18} color="#D1D5DB" />
                </Pressable>
              ))
            )}
          </View>
        </ScrollView>
      </Pressable>
      <PreferencesSheet ref={prefsRef} />
    </SafeAreaView>
  );
}
