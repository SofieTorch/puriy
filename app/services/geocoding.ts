/**
 * Address & place geocoding via Photon (OpenStreetMap-based).
 * Free, no API key needed. Includes POIs (shops, restaurants, universities, etc.).
 */

const PHOTON_URL = 'https://photon.komoot.io/api';

// Bias results toward Cochabamba
const COCHABAMBA_LAT = -17.39;
const COCHABAMBA_LON = -66.16;

export interface GeocodingResult {
  displayName: string;
  shortName: string;
  lon: number;
  lat: number;
}

export async function searchAddress(query: string): Promise<GeocodingResult[]> {
  if (query.trim().length < 3) return [];

  const params = new URLSearchParams({
    q: query,
    limit: '5',
    lat: String(COCHABAMBA_LAT),
    lon: String(COCHABAMBA_LON),
  });

  try {
    const resp = await fetch(`${PHOTON_URL}?${params.toString()}`, {
      headers: { 'User-Agent': 'CbbaMobility/1.0 (transit-app)' },
    });

    if (!resp.ok) return [];

    const data: PhotonResponse = await resp.json();

    return data.features
      .filter((f) => f.geometry?.coordinates?.length === 2)
      .map((f) => ({
        displayName: buildDisplayName(f.properties),
        shortName: buildShortName(f.properties),
        lon: f.geometry.coordinates[0],
        lat: f.geometry.coordinates[1],
      }));
  } catch {
    return [];
  }
}

function buildShortName(p: PhotonProperties): string {
  if (p.name) {
    return p.street ? `${p.name}, ${p.street}` : p.name;
  }
  if (p.street) {
    return p.housenumber ? `${p.street} ${p.housenumber}` : p.street;
  }
  return p.locality ?? p.city ?? 'Sin nombre';
}

function buildDisplayName(p: PhotonProperties): string {
  const parts: string[] = [];
  if (p.name) parts.push(p.name);
  if (p.street) {
    parts.push(p.housenumber ? `${p.street} ${p.housenumber}` : p.street);
  }
  if (p.locality) parts.push(p.locality);
  if (p.city && p.city !== p.locality) parts.push(p.city);
  return parts.length > 0 ? parts.join(', ') : 'Ubicación';
}

interface PhotonProperties {
  name?: string;
  street?: string;
  housenumber?: string;
  locality?: string;
  city?: string;
  county?: string;
  state?: string;
  country?: string;
  osm_key?: string;
  osm_value?: string;
  type?: string;
}

interface PhotonResponse {
  type: string;
  features: Array<{
    type: string;
    properties: PhotonProperties;
    geometry: { type: string; coordinates: [number, number] };
  }>;
}
