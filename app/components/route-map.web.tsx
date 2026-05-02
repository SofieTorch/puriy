/**
 * Web version of RouteMap — renders Leaflet directly in the DOM.
 * On native, react-native-webview is used; on web it shows "not supported",
 * so this file replaces it with a direct Leaflet integration.
 */
import React, { useEffect, useRef, useMemo } from 'react';
import { View, StyleProp, ViewStyle } from 'react-native';

export interface Leg {
  mode: 'bus' | 'walk';
  geometry: [number, number][];
  line_name?: string;
}

export interface LineRoute {
  coordinates: [number, number][];
  name: string;
}

interface RouteMapProps {
  legs?: Leg[];
  lineRoute?: LineRoute | null;
  detourPath?: [number, number][] | null;
  highlightPath?: [number, number][] | null;
  currentLocation?: { lon: number; lat: number } | null;
  style?: StyleProp<ViewStyle>;
}

const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';

let leafletLoaded: Promise<void> | null = null;

function loadLeaflet(): Promise<void> {
  if (leafletLoaded) return leafletLoaded;
  leafletLoaded = new Promise((resolve, reject) => {
    // CSS
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
    }
    // JS
    if ((window as any).L) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = LEAFLET_JS;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Leaflet'));
    document.head.appendChild(script);
  });
  return leafletLoaded;
}

export default function RouteMap({ legs = [], lineRoute, detourPath, highlightPath, currentLocation, style }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  const data = useMemo(
    () => ({ legs, lineRoute: lineRoute ?? null, detourPath: detourPath ?? null, highlightPath: highlightPath ?? null, currentLocation: currentLocation ?? null }),
    [JSON.stringify(legs), JSON.stringify(lineRoute), JSON.stringify(detourPath), JSON.stringify(highlightPath), JSON.stringify(currentLocation)]
  );

  useEffect(() => {
    let cancelled = false;

    loadLeaflet().then(() => {
      if (cancelled || !containerRef.current) return;
      const L = (window as any).L;

      // Destroy previous map
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      // Compute bounds
      let minLat = Infinity, maxLat = -Infinity;
      let minLng = Infinity, maxLng = -Infinity;
      const addToBounds = (lon: number, lat: number) => {
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lon < minLng) minLng = lon;
        if (lon > maxLng) maxLng = lon;
      };

      for (const leg of data.legs) {
        for (const [lng, lat] of leg.geometry) addToBounds(lng, lat);
      }
      if (data.lineRoute) {
        for (const [lng, lat] of data.lineRoute.coordinates) addToBounds(lng, lat);
      }
      if (data.detourPath) {
        for (const [lng, lat] of data.detourPath) addToBounds(lng, lat);
      }
      if (data.currentLocation) {
        addToBounds(data.currentLocation.lon, data.currentLocation.lat);
      }

      const hasCoords = isFinite(minLat);
      const centerLat = hasCoords ? (minLat + maxLat) / 2 : -17.39;
      const centerLng = hasCoords ? (minLng + maxLng) / 2 : -66.16;

      const map = L.map(containerRef.current, { zoomControl: false, attributionControl: false })
        .setView([centerLat, centerLng], 13);
      mapRef.current = map;

      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

      // Route leg polylines
      for (const leg of data.legs) {
        const coords = leg.geometry.map(([lng, lat]: [number, number]) => [lat, lng]);
        const color = leg.mode === 'bus' ? '#09A6F3' : '#9CA3AF';
        const weight = leg.mode === 'bus' ? 5 : 3;
        const opts: any = { color, weight };
        if (leg.mode === 'walk') opts.dashArray = '6 8';
        L.polyline(coords, opts).addTo(map);
      }

      // Line route polyline
      if (data.lineRoute && data.lineRoute.coordinates.length >= 2) {
        const coords = data.lineRoute.coordinates.map(([lng, lat]: [number, number]) => [lat, lng]);
        L.polyline(coords, { color: '#09A6F3', weight: 5 }).addTo(map);
      }

      // Detour path
      if (data.detourPath && data.detourPath.length >= 2) {
        const coords = data.detourPath.map(([lng, lat]: [number, number]) => [lat, lng]);
        L.polyline(coords, { color: '#F97316', weight: 4, dashArray: '8 6' }).addTo(map);
      }

      // Highlighted section (bold blue, for voting)
      if (data.highlightPath && data.highlightPath.length >= 2) {
        const coords = data.highlightPath.map(([lng, lat]: [number, number]) => [lat, lng]);
        L.polyline(coords, { color: '#09A6F3', weight: 7, opacity: 0.9 }).addTo(map);
      }

      // Markers for legs
      if (data.legs.length > 0) {
        const first = data.legs[0].geometry[0];
        if (first) {
          L.circleMarker([first[1], first[0]], { radius: 8, color: '#fff', fillColor: '#22C55E', fillOpacity: 1, weight: 2 }).addTo(map);
        }
        const lastLeg = data.legs[data.legs.length - 1];
        const last = lastLeg.geometry[lastLeg.geometry.length - 1];
        if (last) {
          L.circleMarker([last[1], last[0]], { radius: 8, color: '#fff', fillColor: '#EF4444', fillOpacity: 1, weight: 2 }).addTo(map);
        }
        // Transfer points
        for (let i = 0; i < data.legs.length - 1; i++) {
          const end = data.legs[i].geometry[data.legs[i].geometry.length - 1];
          if (end) {
            L.circleMarker([end[1], end[0]], { radius: 6, color: '#fff', fillColor: '#F97316', fillOpacity: 1, weight: 2 }).addTo(map);
          }
        }
      }

      // Current location dot
      if (data.currentLocation) {
        const { lat, lon } = data.currentLocation;
        L.circleMarker([lat, lon], { radius: 8, color: '#fff', fillColor: '#4285F4', fillOpacity: 1, weight: 3 }).addTo(map);
        L.circle([lat, lon], { radius: 30, color: '#4285F4', fillColor: '#4285F4', fillOpacity: 0.15, weight: 1 }).addTo(map);
      }

      // Fit bounds
      if (hasCoords) {
        map.fitBounds([[minLat, minLng], [maxLat, maxLng]], { padding: [30, 30] });
      }
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [data]);

  return (
    <View style={[{ height: 300 }, style]}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%' }}
      />
    </View>
  );
}
