/**
 * Web version of PickMap — direct DOM Leaflet integration.
 * Mirrors pick-map.tsx: the map pans under a fixed center pin and
 * reports the center coordinate via onMove whenever panning settles.
 */
import React, { useEffect, useRef } from 'react';
import { View, StyleProp, ViewStyle } from 'react-native';

interface PickMapProps {
  initialCenter: { lon: number; lat: number };
  color?: string;
  onMove: (lon: number, lat: number) => void;
  style?: StyleProp<ViewStyle>;
}

const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';

let leafletLoaded: Promise<void> | null = null;

function loadLeaflet(): Promise<void> {
  if (leafletLoaded) return leafletLoaded;
  leafletLoaded = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
    }
    if ((window as any).L) { resolve(); return; }
    const script = document.createElement('script');
    script.src = LEAFLET_JS;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Leaflet'));
    document.head.appendChild(script);
  });
  return leafletLoaded;
}

export default function PickMap({ initialCenter, color = '#D62F3F', onMove, style }: PickMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const frozenCenter = useRef(initialCenter);
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then(() => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const L = (window as any).L;
      const center: [number, number] = [frozenCenter.current.lat, frozenCenter.current.lon];
      const map = L.map(containerRef.current, { zoomControl: false, attributionControl: false }).setView(center, 16);
      mapRef.current = map;
      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { maxZoom: 20, subdomains: 'abcd' }).addTo(map);
      const post = () => {
        const c = map.getCenter();
        onMoveRef.current(c.lng, c.lat);
      };
      map.on('moveend', post);
      post();
    });
    return () => {
      cancelled = true;
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; }
    };
  }, []);

  const pinSvg =
    `<svg viewBox="0 0 24 24" width="36" height="36" fill="${color}" stroke="#fff" stroke-width="1.5" ` +
    `style="filter:drop-shadow(0 3px 4px rgba(0,0,0,0.3))">` +
    `<path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7z"/>` +
    `<circle cx="12" cy="9" r="2.5" fill="#fff" stroke="none"/></svg>`;

  return (
    <View style={[{ flex: 1 }, style]}>
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        <div
          style={{
            position: 'absolute', left: '50%', top: '50%', zIndex: 9999, pointerEvents: 'none',
            transform: 'translate(-50%, -100%)',
          }}
          dangerouslySetInnerHTML={{ __html: pinSvg }}
        />
      </div>
    </View>
  );
}
