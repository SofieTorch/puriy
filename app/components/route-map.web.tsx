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
  color?: string;
  opacity?: number;
  weight?: number;
  focused?: boolean;
}

interface RouteMapProps {
  legs?: Leg[];
  lineRoute?: LineRoute | null;
  lineRoutes?: LineRoute[] | null;
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

export default function RouteMap({ legs = [], lineRoute, lineRoutes, detourPath, highlightPath, currentLocation, style }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  const data = useMemo(
    () => ({ legs, lineRoute: lineRoute ?? null, lineRoutes: lineRoutes ?? null, detourPath: detourPath ?? null, highlightPath: highlightPath ?? null, currentLocation: currentLocation ?? null }),
    [JSON.stringify(legs), JSON.stringify(lineRoute), JSON.stringify(lineRoutes), JSON.stringify(detourPath), JSON.stringify(highlightPath), JSON.stringify(currentLocation)]
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
      for (const lr of data.lineRoutes ?? []) {
        for (const [lng, lat] of lr.coordinates) addToBounds(lng, lat);
      }
      if (data.detourPath) {
        for (const [lng, lat] of data.detourPath) addToBounds(lng, lat);
      }
      if (data.currentLocation) {
        addToBounds(data.currentLocation.lon, data.currentLocation.lat);
      }

      // When a ramal is focused, tighten the map to just that geometry.
      const focusedRoutes = (data.lineRoutes ?? []).filter((lr) => lr.focused);
      if (focusedRoutes.length) {
        minLat = Infinity; maxLat = -Infinity; minLng = Infinity; maxLng = -Infinity;
        for (const lr of focusedRoutes) {
          for (const [lng, lat] of lr.coordinates) addToBounds(lng, lat);
        }
      }

      const hasCoords = isFinite(minLat);
      const centerLat = hasCoords ? (minLat + maxLat) / 2 : -17.39;
      const centerLng = hasCoords ? (minLng + maxLng) / 2 : -66.16;

      const map = L.map(containerRef.current, { zoomControl: false, attributionControl: false })
        .setView([centerLat, centerLng], 13);
      mapRef.current = map;

      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { maxZoom: 20, subdomains: 'abcd' }).addTo(map);

      // When a section is highlighted (voting) the full route is muted context.
      const hasHighlight = !!(data.highlightPath && data.highlightPath.length >= 2);

      // Route leg polylines
      for (const leg of data.legs) {
        const coords = leg.geometry.map(([lng, lat]: [number, number]) => [lat, lng]);
        const color = leg.mode === 'bus' ? '#3D6CB4' : '#9CA3AF';
        const weight = leg.mode === 'bus' ? 5 : 3;
        const opts: any = { color, weight };
        if (leg.mode === 'walk') opts.dashArray = '6 8';
        L.polyline(coords, opts).addTo(map);
      }

      // Line route polyline (muted context while voting, primary otherwise)
      if (data.lineRoute && data.lineRoute.coordinates.length >= 2) {
        const coords = data.lineRoute.coordinates.map(([lng, lat]: [number, number]) => [lat, lng]);
        const opts = hasHighlight
          ? { color: '#6b7280', weight: 5, opacity: 0.45 }
          : { color: '#3D6CB4', weight: 5 };
        L.polyline(coords, opts).addTo(map);
      }

      // Multiple route geometries (every ramal of a line)
      if (data.lineRoutes && data.lineRoutes.length) {
        for (const lr of data.lineRoutes) {
          if (lr.coordinates.length < 2) continue;
          const coords = lr.coordinates.map(([lng, lat]: [number, number]) => [lat, lng]);
          L.polyline(coords, {
            color: lr.color ?? '#3D6CB4',
            weight: lr.weight ?? 5,
            opacity: lr.opacity ?? 0.9,
          }).addTo(map);
        }
      }

      // Detour path
      if (data.detourPath && data.detourPath.length >= 2) {
        const coords = data.detourPath.map(([lng, lat]: [number, number]) => [lat, lng]);
        L.polyline(coords, { color: '#F97316', weight: 4, dashArray: '8 6' }).addTo(map);
      }

      // Highlighted section (bold blue, for voting) + legend
      if (hasHighlight) {
        const coords = data.highlightPath!.map(([lng, lat]: [number, number]) => [lat, lng]);
        L.polyline(coords, { color: '#3D6CB4', weight: 7, opacity: 1 }).addTo(map);

        const legend = new L.Control({ position: 'bottomleft' });
        legend.onAdd = () => {
          const div = L.DomUtil.create('div');
          div.style.cssText = 'background:rgba(255,255,255,.92);border-radius:10px;' +
            'padding:8px 10px;font:12px -apple-system,system-ui,sans-serif;color:#374151;' +
            'box-shadow:0 1px 6px rgba(0,0,0,.15)';
          div.innerHTML =
            '<div style="display:flex;align-items:center;gap:6px">' +
            '<span style="width:16px;height:4px;border-radius:2px;background:#3D6CB4;display:inline-block"></span>Tu sección</div>' +
            '<div style="display:flex;align-items:center;gap:6px;margin-top:4px">' +
            '<span style="width:16px;height:4px;border-radius:2px;background:#6b7280;opacity:.5;display:inline-block"></span>Resto de la ruta</div>';
          return div;
        };
        legend.addTo(map);
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
