import React, { useMemo } from 'react';
import { StyleProp, ViewStyle } from 'react-native';
import { WebView } from 'react-native-webview';

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

export default function RouteMap({ legs = [], lineRoute, detourPath, highlightPath, currentLocation, style }: RouteMapProps) {
  const html = useMemo(
    () => buildMapHtml(legs, currentLocation ?? null, lineRoute ?? null, detourPath ?? null, highlightPath ?? null),
    [JSON.stringify(legs), JSON.stringify(currentLocation), JSON.stringify(lineRoute), JSON.stringify(detourPath), JSON.stringify(highlightPath)]
  );

  return (
    <WebView
      style={[{ height: 300 }, style]}
      source={{ html }}
      scrollEnabled={false}
      overScrollMode="never"
      showsVerticalScrollIndicator={false}
    />
  );
}

function buildMapHtml(
  legs: Leg[],
  currentLocation: { lon: number; lat: number } | null,
  lineRoute: LineRoute | null,
  detourPath: [number, number][] | null,
  highlightPath: [number, number][] | null,
): string {
  let minLat = Infinity, maxLat = -Infinity;
  let minLng = Infinity, maxLng = -Infinity;

  const addToBounds = (lon: number, lat: number) => {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLng) minLng = lon;
    if (lon > maxLng) maxLng = lon;
  };

  for (const leg of legs) {
    for (const [lng, lat] of leg.geometry) addToBounds(lng, lat);
  }
  if (lineRoute) {
    for (const [lng, lat] of lineRoute.coordinates) addToBounds(lng, lat);
  }
  if (currentLocation) {
    addToBounds(currentLocation.lon, currentLocation.lat);
  }

  const hasCoords = isFinite(minLat);
  const centerLat = hasCoords ? (minLat + maxLat) / 2 : -17.39;
  const centerLng = hasCoords ? (minLng + maxLng) / 2 : -66.16;

  // Polylines for route legs
  const polylines = legs.map((leg) => {
    const coords = leg.geometry.map(([lng, lat]) => `[${lat},${lng}]`).join(',');
    const color = leg.mode === 'bus' ? '#09A6F3' : '#9CA3AF';
    const weight = leg.mode === 'bus' ? 5 : 3;
    const dash = leg.mode === 'walk' ? ', dashArray: "6 8"' : '';
    return `L.polyline([${coords}], {color:'${color}', weight:${weight}${dash}}).addTo(map);`;
  }).join('\n');

  // Line route polyline (for nearby line view)
  let lineRouteJs = '';
  if (lineRoute && lineRoute.coordinates.length >= 2) {
    const coords = lineRoute.coordinates.map(([lng, lat]) => `[${lat},${lng}]`).join(',');
    lineRouteJs = `L.polyline([${coords}], {color:'#09A6F3', weight:5}).addTo(map);`;
  }

  // Detour path polyline (orange dashed, overlaid on normal route)
  let detourPathJs = '';
  if (detourPath && detourPath.length >= 2) {
    const coords = detourPath.map(([lng, lat]) => `[${lat},${lng}]`).join(',');
    detourPathJs = `L.polyline([${coords}], {color:'#F97316', weight:4, dashArray:'8 6'}).addTo(map);`;
    for (const [lng, lat] of detourPath) addToBounds(lng, lat);
  }

  // Highlighted section (bold blue, for voting)
  let highlightPathJs = '';
  if (highlightPath && highlightPath.length >= 2) {
    const coords = highlightPath.map(([lng, lat]) => `[${lat},${lng}]`).join(',');
    highlightPathJs = `L.polyline([${coords}], {color:'#09A6F3', weight:7, opacity:0.9}).addTo(map);`;
    for (const [lng, lat] of highlightPath) addToBounds(lng, lat);
  }

  // Markers
  const markers: string[] = [];
  if (legs.length > 0) {
    const first = legs[0].geometry[0];
    if (first) {
      markers.push(`L.circleMarker([${first[1]},${first[0]}], {radius:8, color:'#fff', fillColor:'#22C55E', fillOpacity:1, weight:2}).addTo(map);`);
    }
    const lastLeg = legs[legs.length - 1];
    const last = lastLeg.geometry[lastLeg.geometry.length - 1];
    if (last) {
      markers.push(`L.circleMarker([${last[1]},${last[0]}], {radius:8, color:'#fff', fillColor:'#EF4444', fillOpacity:1, weight:2}).addTo(map);`);
    }
    for (let i = 0; i < legs.length - 1; i++) {
      const end = legs[i].geometry[legs[i].geometry.length - 1];
      if (end) {
        markers.push(`L.circleMarker([${end[1]},${end[0]}], {radius:6, color:'#fff', fillColor:'#F97316', fillOpacity:1, weight:2}).addTo(map);`);
      }
    }
  }

  // Current location blue dot with pulse animation
  let currentLocJs = '';
  if (currentLocation) {
    currentLocJs = `
      L.circleMarker([${currentLocation.lat},${currentLocation.lon}], {
        radius: 8, color: '#fff', fillColor: '#4285F4', fillOpacity: 1, weight: 3
      }).addTo(map);
      L.circle([${currentLocation.lat},${currentLocation.lon}], {
        radius: 30, color: '#4285F4', fillColor: '#4285F4', fillOpacity: 0.15, weight: 1
      }).addTo(map);
    `;
  }

  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body { margin: 0; padding: 0; }
  #map { width: 100%; height: 100vh; }
  #recenter {
    position: fixed;
    bottom: 40%;
    right: 16px;
    z-index: 9999;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: white;
    border: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
  #recenter:active { background: #f3f4f6; }
  #recenter svg { width: 20px; height: 20px; }
</style>
</head>
<body>
<div id="map"></div>
<button id="recenter" onclick="recenter()">
  <svg viewBox="0 0 24 24" fill="none" stroke="#09A6F3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
  </svg>
</button>
<script>
  var bounds = ${hasCoords ? `[[${minLat},${minLng}],[${maxLat},${maxLng}]]` : 'null'};
  var map = L.map('map', {zoomControl: false, attributionControl: false}).setView([${centerLat}, ${centerLng}], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19}).addTo(map);
  ${polylines}
  ${lineRouteJs}
  ${detourPathJs}
  ${highlightPathJs}
  ${markers.join('\n  ')}
  ${currentLocJs}
  if (bounds) map.fitBounds(bounds, {padding: [30,30]});
  function recenter() { if (bounds) map.fitBounds(bounds, {padding: [30,30]}); }
</script>
</body>
</html>`;
}
