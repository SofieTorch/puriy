/**
 * Lightweight interactive map for picking a single coordinate.
 * The map pans under a fixed center pin (Uber-style); whatever the
 * pin points at when panning settles is reported back via onMove.
 *
 * Native uses react-native-webview + Leaflet; pick-map.web.tsx mirrors
 * it with a direct DOM Leaflet integration.
 */
import React, { useMemo, useRef } from 'react';
import { StyleProp, ViewStyle } from 'react-native';
import { WebView } from 'react-native-webview';

interface PickMapProps {
  initialCenter: { lon: number; lat: number };
  /** Pin / accent color (hex). */
  color?: string;
  /** Fired whenever panning settles, with the new center coordinate. */
  onMove: (lon: number, lat: number) => void;
  style?: StyleProp<ViewStyle>;
}

export default function PickMap({ initialCenter, color = '#D62F3F', onMove, style }: PickMapProps) {
  // Build the HTML once. Re-deriving it on every center change would
  // reload the WebView and fight the user's panning, so we freeze the
  // initial center and only depend on the (rarely changing) color.
  const frozenCenter = useRef(initialCenter);
  const html = useMemo(() => buildPickHtml(frozenCenter.current, color), [color]);

  return (
    <WebView
      style={[{ flex: 1 }, style]}
      source={{ html }}
      scrollEnabled={false}
      overScrollMode="never"
      showsVerticalScrollIndicator={false}
      onMessage={(e) => {
        try {
          const { lat, lng } = JSON.parse(e.nativeEvent.data);
          if (typeof lat === 'number' && typeof lng === 'number') onMove(lng, lat);
        } catch {}
      }}
    />
  );
}

function buildPickHtml(center: { lon: number; lat: number }, color: string): string {
  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body { margin: 0; padding: 0; }
  #map { width: 100%; height: 100vh; }
  #pin {
    position: fixed; left: 50%; top: 50%; z-index: 9999; pointer-events: none;
    transform: translate(-50%, -100%);
  }
  #pin svg { width: 36px; height: 36px; display: block; filter: drop-shadow(0 3px 4px rgba(0,0,0,0.3)); }
  #shadow {
    position: fixed; left: 50%; top: 50%; z-index: 9998; pointer-events: none;
    width: 10px; height: 4px; border-radius: 50%; background: rgba(0,0,0,0.25);
    transform: translate(-50%, -1px);
  }
  #recenter {
    position: fixed; top: 45%; right: 16px; z-index: 9999;
    width: 44px; height: 44px; border-radius: 12px; background: white; border: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    display: flex; align-items: center; justify-content: center; cursor: pointer;
  }
  #recenter:active { background: #f3f4f6; }
  #recenter svg { width: 20px; height: 20px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="shadow"></div>
<div id="pin">
  <svg viewBox="0 0 24 24" fill="${color}" stroke="#fff" stroke-width="1.5">
    <path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7z"/>
    <circle cx="12" cy="9" r="2.5" fill="#fff" stroke="none"/>
  </svg>
</div>
<button id="recenter" onclick="recenter()">
  <svg viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
  </svg>
</button>
<script>
  var center = [${center.lat}, ${center.lon}];
  var map = L.map('map', {zoomControl: false, attributionControl: false}).setView(center, 16);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {maxZoom: 20, subdomains: 'abcd'}).addTo(map);
  function post() {
    var c = map.getCenter();
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({lat: c.lat, lng: c.lng}));
    }
  }
  map.on('moveend', post);
  function recenter() { map.setView(center, 16); }
  post();
</script>
</body>
</html>`;
}
