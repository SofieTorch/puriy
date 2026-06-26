import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import Feather from '@expo/vector-icons/Feather';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
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
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import PreferencesSheet from '@/components/preferences-sheet';
import PickMap from '@/components/pick-map';
import RouteMap, { Leg, LineRoute } from '@/components/route-map';
import { palette } from '@/constants/palette';
import api, { DaySchedule, DirectionsLeg, DirectionsResponse, NearbyLineWithRoute } from '@/services/api';
import { getCurrentLocation, watchLocation } from '@/services/current-location';
import { GeocodingResult, reverseGeocode, searchAddress } from '@/services/geocoding';
import { includePendingLines, includePendingRoutes } from '@/services/preferences';
import { saveTrip } from '@/services/saved-trips';
import { SaveTripModal, SaveTripModalResult } from '@/components/save-trip-modal';
import { addToHistory, filterHistory } from '@/services/search-history';
import { SearchHistoryEntry } from '@/db/schema';

const BLUE = palette.blue.DEFAULT;
const RED = palette.red.DEFAULT;

// Vehicle-type icon + label per line_type, shown as a chip on the
// nearby-lines cards. micro = painted city bus, trufi = shared minibus/van,
// taxi_trufi = shared sedan running a fixed route.
const VEHICLE_META = {
  micro: { icon: 'bus', label: 'Micro' },
  trufi: { icon: 'van-passenger', label: 'Trufi' },
  taxi_trufi: { icon: 'taxi', label: 'Taxi trufi' },
} as const;

// Distinct colors for a line's ramales on the map (qualitative palette,
// readable on the light Positron basemap). Cycled if a line has more.
const RAMAL_COLORS = ['#3D6CB4', '#D62F3F', '#1F9D57', '#E8A300', '#7E57C2', '#0CA5A5', '#E0682B'];

// A line's ramal as shown in the detail view: its color, geometry
// (one or more fragments), endpoints, and street summary.
type RamalDetail = {
  label: string;
  color: string;
  segments: [number, number][][];
  streets: string;
  endpointLabel: string | null;
};

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function formatDuration(s: number): string {
  const mins = Math.round(s / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

function formatFareBob(b: number | null | undefined): string | null {
  if (b == null) return null;
  return `Bs. ${b.toFixed(2)}`;
}

function formatFrequency(min: number | null | undefined): string | null {
  if (min == null) return null;
  return `c/ ${min} min`;
}

// "HH:MM:SS" (local Cochabamba time) → "HH:MM"
function formatClock(t: string | null | undefined): string | null {
  return t ? t.slice(0, 5) : null;
}

function todayBucket(): DaySchedule['day_bucket'] {
  const d = new Date().getDay(); // 0 = Sunday, 6 = Saturday
  return d === 0 ? 'sunday' : d === 6 ? 'saturday' : 'weekday';
}

// Schedule for today's day-bucket, falling back to weekday then whatever exists.
function pickSchedule(schedules: DaySchedule[] | undefined): DaySchedule | null {
  if (!schedules || schedules.length === 0) return null;
  const bucket = todayBucket();
  return (
    schedules.find((s) => s.day_bucket === bucket) ??
    schedules.find((s) => s.day_bucket === 'weekday') ??
    schedules[0]
  );
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

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

type ActiveField = 'origin' | 'destination' | null;
type ViewState = 'search' | 'results' | 'detail' | 'line_detail';
type SearchMode = 'text' | 'map';

// Cochabamba centroid — fallback when we have no user location yet.
const CBBA_CENTER = { lon: -66.157, lat: -17.3895 };

export default function ExploreScreen() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const tabBarHeight = useBottomTabBarHeight();

  // Location
  const [userLoc, setUserLoc] = useState<{ lon: number; lat: number } | null>(null);
  const [usingCurrentLoc, setUsingCurrentLoc] = useState(true);

  // Search inputs
  const [originText, setOriginText] = useState('Ubicación actual');
  const [destText, setDestText] = useState('');
  const [originCoords, setOriginCoords] = useState<[number, number] | null>(null);
  const [destCoords, setDestCoords] = useState<[number, number] | null>(null);

  // Search mode (text autocomplete vs. drop-a-pin on the map)
  const [searchMode, setSearchMode] = useState<SearchMode>('text');
  const [pinTarget, setPinTarget] = useState<'origin' | 'destination'>('origin');
  const [pinCenter, setPinCenter] = useState<{ lon: number; lat: number } | null>(null);
  const [pinResolving, setPinResolving] = useState(false);

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
  // Every active ramal for the selected line (fetched on open), plus
  // which one (if any) the user has tapped to focus.
  const [lineRamals, setLineRamals] = useState<RamalDetail[] | null>(null);
  const [focusedRamal, setFocusedRamal] = useState<number | null>(null);
  const [lineDetailLoc, setLineDetailLoc] = useState<{ lon: number; lat: number } | null>(null);
  const [nearbyRadius, setNearbyRadius] = useState(2000);
  const [radiusExpanded, setRadiusExpanded] = useState(false);

  // View state
  const [view, setView] = useState<ViewState>('search');

  // Both the search and results views carry their own blue header band
  // (SBB-style), so the native navigator header is never used here.
  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const prefsRef = useRef<BottomSheet>(null);
  const stepsRef = useRef<BottomSheet>(null);
  const stepsSnapPoints = useMemo(() => ['30%', '70%'], []);

  const canSearch = originCoords !== null && destCoords !== null;

  // Track location as primitive values to avoid object identity issues
  const [userLon, setUserLon] = useState<number | null>(null);
  const [userLat, setUserLat] = useState<number | null>(null);

  const [locationFailed, setLocationFailed] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);

  const fetchLocation = useCallback(async () => {
    setLocationLoading(true);
    setLocationFailed(false);
    const loc = await getCurrentLocation();
    if (loc) {
      setUserLoc(loc);
      setUserLon(loc.lon);
      setUserLat(loc.lat);
      if (usingCurrentLoc) setOriginCoords([loc.lon, loc.lat]);
      setLocationFailed(false);
    } else {
      setLocationFailed(true);
    }
    setLocationLoading(false);
  }, [usingCurrentLoc]);

  // Watch location for real-time updates
  const lastNearbyLoc = useRef<{ lon: number; lat: number } | null>(null);
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    (async () => {
      await fetchLocation();

      unsubscribe = await watchLocation((newLoc) => {
        setUserLoc(newLoc);
        setLocationFailed(false);
        setLocationLoading(false);
        if (usingCurrentLoc) setOriginCoords([newLoc.lon, newLoc.lat]);
        // Only update nearby-fetch coords when user moves >100m to avoid constant refetching
        const prev = lastNearbyLoc.current;
        if (!prev || haversineMeters(prev.lat, prev.lon, newLoc.lat, newLoc.lon) > 100) {
          lastNearbyLoc.current = newLoc;
          setUserLon(newLoc.lon);
          setUserLat(newLoc.lat);
        }
      });
    })();

    return () => { unsubscribe?.(); };
  }, [usingCurrentLoc, fetchLocation]);

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

  // Map-pin mode: confirm the current map center as origin/destination,
  // resolving its address in the background.
  const confirmPin = useCallback(async () => {
    if (!pinCenter || pinResolving) return;
    const { lon, lat } = pinCenter;
    const target = pinTarget;
    setPinResolving(true);
    try {
      const name = await reverseGeocode(lon, lat);
      const label = name || `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
      if (target === 'origin') {
        setOriginCoords([lon, lat]); setOriginText(label); setUsingCurrentLoc(false);
        if (!destCoords) setPinTarget('destination');
      } else {
        setDestCoords([lon, lat]); setDestText(label);
        if (!originCoords) setPinTarget('origin');
      }
      setRoutes([]);
    } finally {
      setPinResolving(false);
    }
  }, [pinCenter, pinResolving, pinTarget, destCoords, originCoords]);

  const swapEndpoints = useCallback(() => {
    setOriginText(destText); setDestText(originText);
    setOriginCoords(destCoords); setDestCoords(originCoords);
    setUsingCurrentLoc(false); setRoutes([]);
  }, [destText, originText, destCoords, originCoords]);

  // Open a nearby line's detail view, fetching every active ramal's
  // geometry so the map shows all branches (not just the first ramal).
  const openLine = useCallback(async (line: NearbyLineWithRoute) => {
    setSelectedLine(line);
    setLineDetailLoc(userLoc);
    setLineRamals(null);
    setFocusedRamal(null);
    setView('line_detail');
    try {
      const fc = await api.getLineRoute(line.line_id);
      const feats = (fc.features ?? []).filter((f) => (f.geometry?.coordinates?.length ?? 0) >= 2);

      // Group fragments by ramal so each ramal is one entry (with its
      // own color), even when split across multiple route fragments.
      const order: string[] = [];
      const byLabel = new Map<string, typeof feats>();
      for (const f of feats) {
        const key = f.properties.ramal_label ?? '';
        if (!byLabel.has(key)) { byLabel.set(key, []); order.push(key); }
        byLabel.get(key)!.push(f);
      }

      const ramals: RamalDetail[] = order.map((key, i) => {
        const group = byLabel.get(key)!.slice().sort(
          (a, b) => a.properties.fragment_index - b.properties.fragment_index,
        );
        const segments = group.map((f) => f.geometry.coordinates as [number, number][]);
        const streetsList: string[] = [];
        for (const f of group) {
          for (const s of f.properties.street_summary ?? []) {
            if (!streetsList.includes(s)) streetsList.push(s);
          }
        }
        const startZone = group[0].properties.endpoint_zones?.[0] ?? null;
        const endZone = group[group.length - 1].properties.endpoint_zones?.[1] ?? null;
        const endpointLabel = startZone && endZone
          ? `${startZone} → ${endZone}`
          : startZone || endZone || null;
        return {
          label: key || `Ramal ${i + 1}`,
          color: RAMAL_COLORS[i % RAMAL_COLORS.length],
          segments,
          streets: streetsList.slice(0, 6).join(' · '),
          endpointLabel,
        };
      });
      setLineRamals(ramals.length ? ramals : null);
    } catch {
      setLineRamals(null);
    }
  }, [userLoc]);

  const selectRoute = useCallback(async (route: DirectionsResponse) => {
    setSelectedRoute(route); setLegNames({}); setLineDetailLoc(userLoc); setView('detail');
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

  const [saveTripModalVisible, setSaveTripModalVisible] = useState(false);

  const handleSaveTrip = useCallback((result: SaveTripModalResult) => {
    if (!selectedRoute || !originCoords || !destCoords) return;
    saveTrip({
      originName: originText,
      destName: destText,
      originCoords,
      destCoords,
      type: result.type,
      route: selectedRoute,
      departureTime: result.departureTime,
    });
    setSaveTripModalVisible(false);
    const message =
      result.type === 'commute'
        ? 'Se mostrará todos los días.'
        : 'Se mostrará solo por hoy.';
    const withTime = result.departureTime
      ? `${message} Te avisaremos a las ${result.departureTime}.`
      : message;
    Alert.alert('Ruta guardada', withTime);
  }, [selectedRoute, originCoords, destCoords, originText, destText]);

  const promptSaveTrip = useCallback(() => {
    setSaveTripModalVisible(true);
  }, []);

  const mapLegs: Leg[] = selectedRoute?.legs.map(l => ({ mode: l.mode, geometry: l.geometry, line_name: l.line_name ?? undefined })) ?? [];

  // Autocomplete dropdown (reused in search + results views)
  const autocompleteDropdown = activeField && (historyItems.length > 0 || suggestions.length > 0) ? (
    <View className="mb-3 rounded-xl border border-brand-line bg-white">
      {historyItems.map(entry => (
        <Pressable key={`h-${entry.id}`} className="flex-row items-center border-b border-gray-100 px-4 py-3" onPress={() => pickHistoryItem(entry)}>
          <Feather name="clock" size={14} color="#9CA3AF" />
          <Text className="ml-2 flex-1 text-sm text-gray-700" numberOfLines={1}>{entry.name}</Text>
        </Pressable>
      ))}
      {suggestions.map((item, i) => (
        <Pressable key={`s-${i}`} className="border-b border-gray-100 px-4 py-3" onPress={() => pickSuggestion(item)}>
          <Text className="text-sm font-medium text-brand-ink" numberOfLines={1}>{item.shortName}</Text>
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
    // One polyline per ramal fragment, colored per ramal. When a ramal
    // is focused, it's emphasized and the others are dimmed.
    const mapLineRoutes: LineRoute[] | null = lineRamals
      ? lineRamals.flatMap((r, i) =>
          r.segments.map((seg) => ({
            coordinates: seg,
            name: r.label,
            color: r.color,
            focused: focusedRamal === i,
            opacity: focusedRamal === null ? 0.9 : focusedRamal === i ? 1 : 0.2,
            weight: focusedRamal === i ? 7 : focusedRamal === null ? 5 : 4,
          })),
        )
      : null;
    return (
      <View accessible={false} className="flex-1">
        <RouteMap
          lineRoute={mapLineRoutes ? null : lr}
          lineRoutes={mapLineRoutes}
          detourPath={selectedLine.detour_alert?.detour_path ?? null}
          currentLocation={lineDetailLoc}
          style={{ flex: 1 }}
        />
        <Pressable className="absolute left-4 rounded-full bg-white p-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={() => { setSelectedLine(null); setLineRamals(null); setFocusedRamal(null); setView('search'); }}>
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>
        <View className="absolute left-4 right-4 items-center rounded-2xl bg-white px-5 py-3 shadow-lg" style={{ top: insets.top + 60 }}>
          <Text className="text-base font-bold text-[#3D6CB4]">Línea {selectedLine.line_name}</Text>
          {selectedLine.line_description && <Text className="text-xs text-gray-400">{selectedLine.line_description}</Text>}
          {selectedLine.ramales && selectedLine.ramales.length > 1 && (
            <Text className="mt-0.5 text-xs text-brand-muted">{selectedLine.ramales.length} ramales</Text>
          )}
          {(() => {
            const sch = pickSchedule(selectedLine.schedules);
            const start = formatClock(sch?.service_start_at);
            const end = formatClock(sch?.service_end_at);
            const hours = start && end ? `${start}–${end}` : null;
            const freq = sch?.headway_min != null ? `cada ${sch.headway_min} min` : null;
            if (!hours && !freq) return null;
            return (
              <View className="mt-1.5 flex-row items-center gap-1.5">
                <Feather name="clock" size={13} color={palette.muted} />
                <Text className="text-xs text-brand-muted">{[hours, freq].filter(Boolean).join(' · ')}</Text>
              </View>
            );
          })()}
        </View>
        {selectedLine.detour_alert && (
          <View className="absolute left-4 right-4 flex-row items-center rounded-2xl bg-orange-50 px-4 py-3 shadow-lg" style={{ top: insets.top + 115 }}>
            <Feather name="alert-triangle" size={16} color="#F97316" />
            <View className="ml-3 flex-1">
              <Text className="text-sm font-semibold text-orange-600">
                Desvío {selectedLine.detour_alert.reason ? `por ${selectedLine.detour_alert.reason}` : 'activo'}
              </Text>
              {selectedLine.detour_alert.diverges_at && selectedLine.detour_alert.rejoins_at && (
                <Text className="text-xs text-orange-500">
                  Desde {selectedLine.detour_alert.diverges_at} hasta {selectedLine.detour_alert.rejoins_at}
                </Text>
              )}
            </View>
          </View>
        )}
        {/* Streets-summary card — tap a ramal to focus it on the map */}
        {lineRamals && lineRamals.length > 0 && (
          <View
            className="absolute left-3 right-3 rounded-2xl bg-white"
            style={{ bottom: tabBarHeight + 12, maxHeight: 240, shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 14, shadowOffset: { width: 0, height: 4 }, elevation: 8 }}
          >
            <ScrollView contentContainerStyle={{ padding: 6 }} showsVerticalScrollIndicator={false}>
              {lineRamals.map((r, i) => {
                const active = focusedRamal === i;
                return (
                  <Pressable
                    key={`${r.label}-${i}`}
                    testID={`ramal-row-${i}`}
                    className={`flex-row items-center rounded-xl px-3 py-2.5 ${active ? 'bg-brand-bg' : ''}`}
                    onPress={() => setFocusedRamal(active ? null : i)}
                  >
                    <View style={{ backgroundColor: r.color }} className="mr-3 h-9 w-1.5 rounded-full" />
                    <View className="flex-1">
                      <Text className="text-sm font-semibold text-brand-ink" numberOfLines={1}>
                        {r.endpointLabel ?? r.label}
                      </Text>
                      {r.streets ? (
                        <Text className="mt-0.5 text-xs text-brand-muted" numberOfLines={active ? 4 : 1}>
                          {r.streets}
                        </Text>
                      ) : null}
                    </View>
                    <Feather name={active ? 'x' : 'chevron-right'} size={16} color={active ? r.color : palette.hint} />
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>
        )}
      </View>
    );
  }

  // ================================================================
  // ROUTE DETAIL VIEW
  // ================================================================
  if (view === 'detail' && selectedRoute) {
    return (
      <View accessible={false} className="flex-1">
        <RouteMap legs={mapLegs} currentLocation={lineDetailLoc} style={{ flex: 1 }} />
        <Pressable className="absolute left-4 rounded-full bg-white p-3 shadow-lg" style={{ top: insets.top + 8 }} onPress={() => setView('results')}>
          <Feather name="arrow-left" size={22} color="#333" />
        </Pressable>
        <Pressable className="absolute right-4 flex-row items-center rounded-full bg-white px-4 py-3 shadow-lg" style={{ top: insets.top + 8 }} testID="explore-save-btn" onPress={promptSaveTrip}>
          <Feather name="bookmark" size={18} color={BLUE} />
          <Text className="ml-2 text-sm font-semibold text-[#3D6CB4]">Guardar</Text>
        </Pressable>
        <SaveTripModal
          visible={saveTripModalVisible}
          onCancel={() => setSaveTripModalVisible(false)}
          onSave={handleSaveTrip}
        />
        <View className="absolute left-4 right-4 rounded-2xl bg-white px-5 py-3 shadow-lg" style={{ top: insets.top + 60 }}>
          <View className="flex-row items-center justify-center gap-2">
            <Text className="text-base font-bold text-brand-ink">{formatDuration(selectedRoute.total_duration_s)} · {formatDistance(selectedRoute.total_distance_m)}</Text>
            {formatFareBob(selectedRoute.total_fare_bob) && (
              <Text className="rounded bg-brand-yellow px-2 py-0.5 text-xs font-semibold text-brand-yellow-ink">{formatFareBob(selectedRoute.total_fare_bob)}</Text>
            )}
          </View>
          <Text className="mt-0.5 text-center text-xs text-brand-hint">{originText} → {destText}</Text>
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
                    <Text className="text-base font-semibold text-brand-ink">Caminar</Text>
                    <Text className="text-sm text-gray-400">{formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}</Text>
                  </View>
                </View>
              );
              const names = legNames[index];
              const fareText = formatFareBob(leg.fare_bob);
              const freqText = formatFrequency(leg.frequency_min);
              return (
                <View key={`b-${index}`}>
                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-[#E7EEF7]"><Feather name="log-in" size={14} color={BLUE} /></View><View className="w-0.5 flex-1 bg-[#3D6CB4]" /></View>
                    <View className="flex-1 pb-2"><Text className="text-base font-semibold text-[#3D6CB4]">Tomar Línea {leg.line_name ?? '?'}</Text><Text className="text-sm text-gray-500">{names ? `en ${names.board}` : 'Cargando...'}</Text></View>
                  </View>
                  <View className="flex-row"><View className="mr-4 w-8 items-center"><View className="w-0.5 flex-1 bg-[#3D6CB4]" /></View>
                    <View className="flex-1 py-1 pb-2">
                      <Text className="text-xs text-gray-400">{formatDistance(leg.distance_m)} · {formatDuration(leg.duration_s)}</Text>
                      <View className="mt-1.5 flex-row flex-wrap items-center gap-2">
                        {fareText ? (
                          <View className="rounded-md bg-brand-yellow px-2.5 py-1">
                            <Text className="text-xs font-semibold text-brand-yellow-ink" testID={`leg-${index}-fare`}>{fareText}</Text>
                          </View>
                        ) : (
                          <Text className="text-xs text-brand-hint" testID={`leg-${index}-fare`}>Tarifa no disponible</Text>
                        )}
                        {freqText && <Text className="text-xs text-gray-400">{freqText}</Text>}
                      </View>
                    </View>
                  </View>
                  <View className="flex-row">
                    <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-[#E7EEF7]"><Feather name="log-out" size={14} color={BLUE} /></View>{!isLast && <View className="w-0.5 flex-1 bg-gray-200" />}</View>
                    <View className="flex-1 pb-5"><Text className="text-base font-semibold text-brand-ink">Bajar</Text><Text className="text-sm text-gray-500">{names ? `en ${names.alight}` : 'Cargando...'}</Text></View>
                  </View>
                </View>
              );
            })}
            <View className="flex-row">
              <View className="mr-4 w-8 items-center"><View className="h-8 w-8 items-center justify-center rounded-full bg-red-100"><Feather name="map-pin" size={14} color="#EF4444" /></View></View>
              <View className="flex-1"><Text className="text-base font-semibold text-brand-ink">Llegaste</Text><Text className="text-sm text-gray-400">{destText}</Text></View>
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
        <View className="flex-1 bg-brand-bg">
          {/* Blue header band */}
          <View style={{ paddingTop: insets.top + 10 }} className="rounded-b-3xl bg-brand-blue px-5 pb-14">
            <View className="flex-row items-center">
              <Pressable className="-ml-1 mr-1 p-1" testID="explore-results-back" onPress={() => setView('search')}>
                <Feather name="arrow-left" size={24} color="#fff" />
              </Pressable>
              <Text className="text-xl font-semibold text-white">Cómo llegar</Text>
            </View>
          </View>

          {/* Floating origin/destination card overlapping the header */}
          <View accessible={false} className="px-5" style={{ marginTop: -36 }}>
            <View
              className="flex-row items-center rounded-2xl border border-brand-line bg-white"
              style={{ shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6 }}
            >
              <View className="flex-1">
                <View className="flex-row items-center px-4">
                  <View className={`h-3 w-3 rounded-full ${originCoords ? 'bg-brand-blue' : 'border-2 border-brand-blue'}`} />
                  <TextInput className="ml-3 flex-1 py-3 text-sm text-brand-ink" placeholder="Punto de partida" placeholderTextColor={palette.hint} value={originText} onChangeText={handleOriginChange} onFocus={() => setActiveField('origin')} />
                </View>
                <View className="ml-9 h-px bg-brand-line" />
                <View className="flex-row items-center px-4">
                  <View className={`h-3 w-3 rounded-sm ${destCoords ? 'bg-brand-red' : 'border-2 border-brand-red'}`} />
                  <TextInput className="ml-3 flex-1 py-3 text-sm text-brand-ink" placeholder="Destino" placeholderTextColor={palette.hint} value={destText} onChangeText={handleDestChange} onFocus={() => setActiveField('destination')} />
                </View>
              </View>
              <View className="mr-2 items-center justify-center gap-2 py-2">
                <Pressable testID="swap-button" className="h-9 w-9 items-center justify-center rounded-full border border-brand-line" onPress={swapEndpoints}>
                  <MaterialCommunityIcons name="swap-vertical" size={17} color={RED} />
                </Pressable>
                <Pressable className={`h-9 w-9 items-center justify-center rounded-full ${canSearch ? 'bg-brand-blue active:opacity-90' : 'bg-[#A9C2E4]'}`} testID="explore-search-btn" onPress={handleSearch} disabled={!canSearch || loading}>
                  {loading ? <ActivityIndicator size="small" color="#fff" /> : <Feather name="search" size={15} color="#fff" />}
                </Pressable>
              </View>
            </View>
            {autocompleteDropdown}
          </View>
          <ScrollView accessible={false} className="flex-1 px-5 pt-4" contentContainerStyle={{ paddingBottom: tabBarHeight + 12 }}>
            <Text className="mb-3 text-lg font-semibold text-brand-ink" testID="explore-results-title">Rutas disponibles</Text>
            {routes.map((route, idx) => {
              const s = routeSummary(route.legs);
              const fareText = formatFareBob(route.total_fare_bob);
              const firstBus = route.legs.find((l) => l.mode === 'bus');
              const primaryFreq = firstBus ? formatFrequency(firstBus.frequency_min) : null;
              return (
                <Pressable key={idx} className="mb-3 rounded-2xl border border-brand-line bg-white p-4 active:bg-gray-50" onPress={() => selectRoute(route)}>
                  {route.legs.some(l => l.detour_alert) && (
                    <View className="mb-2 flex-row items-center rounded-lg bg-brand-red-soft px-3 py-2">
                      <Feather name="alert-triangle" size={14} color={RED} />
                      <Text className="ml-2 text-xs font-semibold text-brand-red-ink">
                        Desvío activo en {route.legs.filter(l => l.detour_alert).map(l => `Línea ${l.line_name}`).join(', ')}
                      </Text>
                    </View>
                  )}
                  <View className="mb-1 h-4 flex-row items-center justify-between">
                    {idx === 0
                      ? <Text className="text-xs font-semibold text-brand-red">Más rápida</Text>
                      : <View />}
                    {primaryFreq && <Text className="text-xs text-brand-hint">{primaryFreq}</Text>}
                  </View>
                  <View className="mb-3 flex-row items-end justify-between">
                    <View className="flex-row items-baseline gap-2">
                      <Text className="text-2xl font-semibold text-brand-ink">{formatDuration(route.total_duration_s)}</Text>
                      <Text className="text-xs text-brand-hint">{formatDistance(route.total_distance_m)}</Text>
                    </View>
                    {fareText && (
                      <Text className="rounded-md bg-brand-yellow px-3 py-1 text-sm font-semibold text-brand-yellow-ink" testID={`route-${idx}-total-fare`}>
                        {fareText}
                      </Text>
                    )}
                  </View>
                  <View className="mb-3 flex-row items-center gap-1">
                    {route.legs.map((leg, i) => <View key={i} className={`h-1.5 rounded-full ${leg.mode === 'bus' ? 'bg-brand-blue' : 'bg-brand-line'}`} style={{ flex: leg.distance_m, minWidth: 8 }} />)}
                  </View>
                  <View className="flex-row flex-wrap items-center gap-2">
                    {route.legs.filter(l => l.mode === 'bus' && l.line_name).map((leg, i) => (
                      <View key={`bus-${i}-${leg.line_name}`} className="flex-row items-center rounded-md bg-brand-blue px-2.5 py-1">
                        <Feather name="truck" size={11} color="#fff" />
                        <Text className="ml-1 text-xs font-semibold text-white">{leg.line_name}</Text>
                      </View>
                    ))}
                    {s.transfers > 0 && <Text className="text-xs text-brand-hint">{s.transfers} transbordo{s.transfers > 1 ? 's' : ''}</Text>}
                    {s.walkMin > 0 && (
                      <View className="flex-row items-center gap-1">
                        <Feather name="navigation" size={11} color={palette.hint} />
                        <Text className="text-xs text-brand-hint">{s.walkMin} min</Text>
                      </View>
                    )}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
    );
  }

  // ================================================================
  // SEARCH VIEW
  // ================================================================
  const pinInitialCenter = userLoc ?? (originCoords ? { lon: originCoords[0], lat: originCoords[1] } : CBBA_CENTER);
  const bothSet = originCoords !== null && destCoords !== null;

  return (
      <View className="flex-1 bg-brand-bg">
        {/* Blue header band — title, settings, and search-mode pills */}
        <View style={{ paddingTop: insets.top + 10 }} className="rounded-b-3xl bg-brand-blue px-5 pb-14">
          <View className="mb-4 flex-row items-center justify-between">
            <Text className="text-2xl font-semibold text-white">Planea tu viaje</Text>
            <Pressable className="h-10 w-10 items-center justify-center rounded-xl bg-white/20" testID="explore-prefs-gear" onPress={() => prefsRef.current?.expand()}>
              <Feather name="settings" size={20} color="#fff" />
            </Pressable>
          </View>
          <View className="flex-row gap-1 rounded-full bg-white/20 p-1">
            {(['text', 'map'] as const).map((mode) => {
              const active = searchMode === mode;
              return (
                <Pressable
                  key={mode}
                  testID={`explore-mode-${mode}`}
                  className={`flex-1 flex-row items-center justify-center gap-1.5 rounded-full py-2 ${active ? 'bg-white' : ''}`}
                  onPress={() => {
                    if (mode === 'map') setPinTarget(originCoords && !destCoords ? 'destination' : 'origin');
                    setSearchMode(mode);
                  }}
                >
                  <Feather name={mode === 'text' ? 'search' : 'map-pin'} size={15} color={active ? BLUE : '#fff'} />
                  <Text className={`text-sm font-semibold ${active ? 'text-brand-blue-ink' : 'text-white'}`}>
                    {mode === 'text' ? 'Buscar' : 'En el mapa'}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {searchMode === 'text' ? (
        <ScrollView
          accessible={false}
          className="flex-1 px-5"
          style={{ marginTop: -36 }}
          contentContainerStyle={{ paddingBottom: tabBarHeight + 12 }}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
         
        >
          <View
            className="mb-4 flex-row items-center rounded-2xl border border-brand-line bg-white"
            style={{ shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6 }}
          >
            <View className="flex-1">
              <View className="flex-row items-center px-4">
                <View className={`h-3 w-3 rounded-full ${originCoords ? 'bg-brand-blue' : 'border-2 border-brand-blue'}`} />
                <TextInput
                  className="ml-3 flex-1 py-4 text-base text-brand-ink"
                  testID="explore-origin-input"
                  placeholder="Punto de partida"
                  placeholderTextColor={palette.hint}
                  value={originText}
                  onChangeText={handleOriginChange}
                  onFocus={() => setActiveField('origin')}
                />
              </View>
              <View className="ml-9 h-px bg-brand-line" />
              <View className="flex-row items-center px-4">
                <View className={`h-3 w-3 rounded-sm ${destCoords ? 'bg-brand-red' : 'border-2 border-brand-red'}`} />
                <TextInput testID="explore-dest-input" className="ml-3 flex-1 py-4 text-base text-brand-ink" placeholder="Destino" placeholderTextColor={palette.hint} value={destText} onChangeText={handleDestChange} onFocus={() => setActiveField('destination')} />
              </View>
            </View>
            <Pressable testID="swap-button" className="mx-2 h-10 w-10 items-center justify-center rounded-full border border-brand-line" onPress={swapEndpoints}>
              <MaterialCommunityIcons name="swap-vertical" size={20} color={RED} />
            </Pressable>
          </View>

          {autocompleteDropdown}

          <Pressable
            className={`mb-6 h-14 flex-row items-center justify-center gap-2 rounded-xl ${canSearch ? 'bg-brand-blue active:opacity-90' : 'bg-[#A9C2E4]'}`}
            testID="explore-search-btn" onPress={handleSearch}
            disabled={!canSearch || loading}
          >
            {loading ? <ActivityIndicator color="#FFFFFF" /> : <><Feather name="search" size={18} color="#fff" /><Text className="text-base font-semibold text-white">Buscar ruta</Text></>}
          </Pressable>

          {/* Nearby lines */}
          <View accessible={false} className="mb-6">
            <Pressable
              testID="explore-nearby-title"
              className="mb-3 flex-row items-center justify-between"
              onPress={() => setRadiusExpanded(!radiusExpanded)}
            >
              <Text className="text-lg font-semibold text-brand-ink">Líneas cercanas</Text>
              <View className="flex-row items-center gap-1">
                <Text className="text-sm text-gray-400">{nearbyRadius >= 1000 ? `${(nearbyRadius / 1000).toFixed(1)} km` : `${nearbyRadius} m`}</Text>
                <Feather name={radiusExpanded ? 'chevron-up' : 'chevron-down'} size={16} color="#9CA3AF" />
              </View>
            </Pressable>

            {radiusExpanded && (
              <View className="mb-3 rounded-xl border border-brand-line bg-gray-50 p-3">
                <Text className="mb-2 text-xs font-medium text-gray-500">Radio de búsqueda</Text>
                <View className="mb-2 flex-row gap-2">
                  {[500, 1000, 2000, 5000].map(r => (
                    <Pressable
                      key={r}
                      className={`flex-1 items-center rounded-lg py-2 ${nearbyRadius === r ? 'bg-[#3D6CB4]' : 'bg-white border border-brand-line'}`}
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
            {locationLoading || nearbyLoading ? (
              <View className="items-center py-4">
                <ActivityIndicator size="small" color={BLUE} />
                <Text className="mt-2 text-sm text-gray-400">
                  {locationLoading ? 'Obteniendo ubicación...' : 'Buscando líneas...'}
                </Text>
              </View>
            ) : locationFailed ? (
              <View className="items-center py-4">
                <Feather name="map-pin" size={24} color="#D1D5DB" />
                <Text className="mt-2 text-sm text-gray-400">No se pudo obtener tu ubicación.</Text>
                <Pressable
                  className="mt-3 rounded-xl bg-[#3D6CB4] px-6 py-2.5"
                  onPress={fetchLocation}
                >
                  <Text className="text-sm font-semibold text-white">Reintentar</Text>
                </Pressable>
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
                    testID="explore-prefs-gear" onPress={() => prefsRef.current?.expand()}
                  >
                    <Text className="text-sm text-amber-700">
                      Hay líneas pendientes cerca. Toca aquí para activar «Incluir líneas pendientes» en preferencias.
                    </Text>
                  </Pressable>
                )}
              </View>
            ) : (
              nearbyLines.map(line => (
                <Pressable
                  key={line.line_id}
                  className="mb-2 flex-row items-center rounded-xl border border-brand-line bg-white px-4 py-3 active:bg-gray-50"
                  onPress={() => openLine(line)}
                >
                  <View className="mr-3 h-10 w-10 items-center justify-center rounded-xl bg-brand-blue px-1">
                    <Text className="text-sm font-semibold text-white" numberOfLines={1}>{line.line_name}</Text>
                  </View>
                  <View className="flex-1">
                    <View className="flex-row items-center">
                      <Text className="text-base font-semibold text-brand-ink">Línea {line.line_name}</Text>
                      {line.line_type && VEHICLE_META[line.line_type] && (
                        <View className="ml-2 flex-row items-center rounded-full bg-gray-100 px-2 py-0.5">
                          <MaterialCommunityIcons name={VEHICLE_META[line.line_type].icon} size={12} color={palette.muted} />
                          <Text className="ml-1 text-[10px] font-semibold text-brand-muted">{VEHICLE_META[line.line_type].label}</Text>
                        </View>
                      )}
                      {line.detour_alert && (
                        <View className="ml-2 flex-row items-center rounded-md bg-orange-50 px-2 py-0.5">
                          <Feather name="alert-triangle" size={10} color="#F97316" />
                          <Text className="ml-1 text-[10px] font-semibold text-orange-500">Desvío</Text>
                        </View>
                      )}
                    </View>
                    {(() => {
                      const ramal = line.ramales?.[0];
                      const [start, end] = ramal?.endpoint_zones ?? [null, null];
                      const endpointLabel = start && end ? `${start} → ${end}` : start || end || null;
                      const streetsLabel = ramal?.street_summary?.slice(0, 4).join(' · ') || null;
                      return (
                        <>
                          {endpointLabel ? (
                            <Text className="text-sm font-medium text-gray-700" numberOfLines={1}>{endpointLabel}</Text>
                          ) : line.line_description && (
                            <Text className="text-sm text-gray-500" numberOfLines={1}>{line.line_description}</Text>
                          )}
                          {streetsLabel && (
                            <Text className="text-xs text-gray-400" numberOfLines={1}>{streetsLabel}</Text>
                          )}
                          {line.ramales && line.ramales.length > 1 && (
                            <Text className="mt-0.5 text-[10px] text-gray-400">
                              {line.ramales.length} ramales
                            </Text>
                          )}
                        </>
                      );
                    })()}
                    {line.detour_alert && (
                      <Text className="mt-0.5 text-xs text-orange-500">
                        {line.detour_alert.diverges_at && line.detour_alert.rejoins_at
                          ? `Desde ${line.detour_alert.diverges_at} hasta ${line.detour_alert.rejoins_at}`
                          : `Por ${line.detour_alert.reason ?? 'causa desconocida'}`}
                      </Text>
                    )}
                  </View>
                  <Feather name="chevron-right" size={18} color="#D1D5DB" />
                </Pressable>
              ))
            )}
          </View>
        </ScrollView>
        ) : (
          <View className="flex-1">
            <PickMap
              initialCenter={pinInitialCenter}
              onMove={(lon, lat) => setPinCenter({ lon, lat })}
              style={{ flex: 1 }}
            />
            {/* Origin / destination selector floating over the map */}
            <View
              className="absolute left-4 right-4 top-3 rounded-2xl border border-brand-line bg-white"
              style={{ shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6 }}
            >
              <Pressable
                className={`flex-row items-center rounded-t-2xl px-4 py-3 ${pinTarget === 'origin' ? 'bg-brand-blue-soft' : ''}`}
                testID="explore-pin-origin-row"
                onPress={() => setPinTarget('origin')}
              >
                <View className={`h-3 w-3 rounded-full ${originCoords ? 'bg-brand-blue' : 'border-2 border-brand-blue'}`} />
                <Text className={`ml-3 flex-1 text-sm ${originCoords ? 'font-medium text-brand-ink' : 'text-brand-hint'}`} numberOfLines={1}>
                  {originCoords ? originText : 'Elige tu origen'}
                </Text>
              </Pressable>
              <View className="ml-9 h-px bg-brand-line" />
              <Pressable
                className={`flex-row items-center rounded-b-2xl px-4 py-3 ${pinTarget === 'destination' ? 'bg-brand-red-soft' : ''}`}
                testID="explore-pin-dest-row"
                onPress={() => setPinTarget('destination')}
              >
                <View className={`h-3 w-3 rounded-sm ${destCoords ? 'bg-brand-red' : 'border-2 border-brand-red'}`} />
                <Text className={`ml-3 flex-1 text-sm ${destCoords ? 'font-medium text-brand-ink' : 'text-brand-hint'}`} numberOfLines={1}>
                  {destCoords ? destText : 'Elige tu destino'}
                </Text>
              </Pressable>
            </View>
            {/* Bottom action(s) */}
            <View className="absolute left-4 right-4" style={{ bottom: tabBarHeight + 16 }}>
              {bothSet && (
                <Pressable
                  className="mb-2 h-14 flex-row items-center justify-center gap-2 rounded-xl bg-brand-blue active:opacity-90"
                  testID="explore-map-search-btn"
                  onPress={handleSearch}
                  disabled={loading}
                >
                  {loading ? <ActivityIndicator color="#fff" /> : <><Feather name="search" size={18} color="#fff" /><Text className="text-base font-semibold text-white">Buscar ruta</Text></>}
                </Pressable>
              )}
              <Pressable
                className={`flex-row items-center justify-center gap-2 rounded-xl ${bothSet ? 'border border-brand-line bg-white' : 'bg-brand-blue active:opacity-90'}`}
                style={{ height: 52 }}
                testID="explore-pin-confirm-btn"
                onPress={confirmPin}
                disabled={pinResolving || !pinCenter}
              >
                {pinResolving ? (
                  <ActivityIndicator color={bothSet ? BLUE : '#fff'} />
                ) : (
                  <>
                    <Feather name="map-pin" size={18} color={bothSet ? BLUE : '#fff'} />
                    <Text className={`text-base font-semibold ${bothSet ? 'text-brand-blue-ink' : 'text-white'}`}>
                      {pinTarget === 'origin' ? 'Confirmar origen' : 'Confirmar destino'}
                    </Text>
                  </>
                )}
              </Pressable>
            </View>
          </View>
        )}
        <PreferencesSheet ref={prefsRef} />
      </View>
  );
}
