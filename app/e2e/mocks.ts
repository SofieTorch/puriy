/**
 * Mock API data for e2e tests.
 * All coordinates are real Cochabamba locations for realistic map rendering.
 */
import type { Page } from '@playwright/test';

// ── Nearby lines ─────────────────────────────────────────────────────────────

export const NEARBY_LINES = [
  {
    line_id: 'line-101',
    line_name: '101',
    line_description: 'Cala Cala - Zona Sur',
    route_geojson: {
      type: 'LineString',
      coordinates: [
        [-66.1568, -17.3895],
        [-66.1550, -17.3880],
        [-66.1530, -17.3870],
        [-66.1510, -17.3860],
        [-66.1490, -17.3850],
      ],
    },
    detour_alert: null,
  },
  {
    line_id: 'line-110',
    line_name: '110',
    line_description: 'Colcapirhua - Centro',
    route_geojson: {
      type: 'LineString',
      coordinates: [
        [-66.1600, -17.3920],
        [-66.1580, -17.3910],
        [-66.1560, -17.3900],
        [-66.1540, -17.3890],
      ],
    },
    detour_alert: null,
  },
];

// ── Directions ───────────────────────────────────────────────────────────────

export const DIRECTIONS_RESPONSE = {
  legs: [
    {
      mode: 'walk' as const,
      line_name: null,
      line_id: null,
      geometry: [
        [-66.1568, -17.3895],
        [-66.1560, -17.3890],
      ],
      distance_m: 120,
      duration_s: 90,
      detour_alert: null,
    },
    {
      mode: 'bus' as const,
      line_name: '101',
      line_id: 'line-101',
      geometry: [
        [-66.1560, -17.3890],
        [-66.1540, -17.3880],
        [-66.1520, -17.3870],
        [-66.1500, -17.3860],
        [-66.1480, -17.3845],
        [-66.1460, -17.3830],
      ],
      distance_m: 2400,
      duration_s: 480,
      detour_alert: null,
    },
    {
      mode: 'walk' as const,
      line_name: null,
      line_id: null,
      geometry: [
        [-66.1460, -17.3830],
        [-66.1455, -17.3825],
      ],
      distance_m: 80,
      duration_s: 60,
      detour_alert: null,
    },
  ],
  total_distance_m: 2600,
  total_duration_s: 630,
};

// ── Geocoding ────────────────────────────────────────────────────────────────

export const GEOCODING_RESULTS = {
  'Plaza Colón': {
    features: [
      {
        geometry: { coordinates: [-66.1575, -17.3935], type: 'Point' },
        properties: {
          name: 'Plaza Colón',
          street: 'Av. Ballivián',
          city: 'Cochabamba',
          state: 'Cochabamba',
          country: 'Bolivia',
        },
      },
    ],
  },
  'Mercado Calatayud': {
    features: [
      {
        geometry: { coordinates: [-66.1460, -17.3825], type: 'Point' },
        properties: {
          name: 'Mercado Calatayud',
          street: 'Calle Lanza',
          city: 'Cochabamba',
          state: 'Cochabamba',
          country: 'Bolivia',
        },
      },
    ],
  },
};

export const REVERSE_GEOCODE_RESPONSE = {
  address: {
    road: 'Avenida Heroínas',
    city: 'Cochabamba',
    state: 'Cochabamba',
    country: 'Bolivia',
  },
  display_name: 'Avenida Heroínas, Cochabamba, Bolivia',
};

// ── Voting ───────────────────────────────────────────────────────────────────

export const PENDING_LINES = [
  {
    line_id: 'line-205',
    line_name: '205',
    line_description: 'Tiquipaya - Centro',
    route_id: 'route-205-1',
    pending_edge_count: 3,
    total_edge_count: 15,
  },
];

export const NEARBY_VOTE_LINES = [
  {
    line_id: 'line-101',
    line_name: '101',
    line_description: 'Cala Cala - Zona Sur',
  },
];

export const VOTEABLE_SEGMENT = {
  route_id: 'route-205-1',
  line_name: '205',
  line_description: 'Tiquipaya - Centro',
  route_geojson: {
    type: 'Feature',
    geometry: {
      type: 'LineString',
      coordinates: [
        [-66.160, -17.392],
        [-66.158, -17.390],
        [-66.156, -17.389],
        [-66.154, -17.388],
        [-66.152, -17.387],
        [-66.150, -17.386],
      ],
    },
  },
  sections: [
    {
      section_index: 0,
      edges: [
        { id: 'edge-1', sequence: 0, valhalla_edge_id: 12345, path: [[-66.158, -17.390], [-66.156, -17.389]], confidence: 0.65, status: 'pending', votes_for: 3, votes_against: 1 },
        { id: 'edge-2', sequence: 1, valhalla_edge_id: 12346, path: [[-66.156, -17.389], [-66.154, -17.388]], confidence: 0.70, status: 'pending', votes_for: 2, votes_against: 0 },
      ],
      trip_count: 3,
      geometry: [[-66.158, -17.390], [-66.156, -17.389], [-66.154, -17.388]],
    },
    {
      section_index: 1,
      edges: [
        { id: 'edge-4', sequence: 3, valhalla_edge_id: 12348, path: [[-66.152, -17.387], [-66.150, -17.386]], confidence: 0.80, status: 'pending', votes_for: 4, votes_against: 0 },
      ],
      trip_count: 2,
      geometry: [[-66.152, -17.387], [-66.150, -17.386]],
    },
  ],
  edges: [
    { id: 'edge-1', sequence: 0, valhalla_edge_id: 12345, path: [[-66.158, -17.390], [-66.156, -17.389]], confidence: 0.65, status: 'pending', votes_for: 3, votes_against: 1 },
    { id: 'edge-2', sequence: 1, valhalla_edge_id: 12346, path: [[-66.156, -17.389], [-66.154, -17.388]], confidence: 0.70, status: 'pending', votes_for: 2, votes_against: 0 },
    { id: 'edge-4', sequence: 3, valhalla_edge_id: 12348, path: [[-66.152, -17.387], [-66.150, -17.386]], confidence: 0.80, status: 'pending', votes_for: 4, votes_against: 0 },
  ],
  segment_geojson: null,
};

// ── Lines list ───────────────────────────────────────────────────────────────

export const LINES = [
  {
    id: 'line-101',
    name: '101',
    description: 'Cala Cala - Zona Sur',
    status: 'approved',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-06-01T00:00:00Z',
  },
  {
    id: 'line-110',
    name: '110',
    description: 'Colcapirhua - Centro',
    status: 'approved',
    created_at: '2025-01-15T00:00:00Z',
    updated_at: '2025-06-15T00:00:00Z',
  },
  {
    id: 'line-205',
    name: '205',
    description: 'Tiquipaya - Centro',
    status: 'pending',
    created_at: '2025-03-01T00:00:00Z',
    updated_at: '2025-07-01T00:00:00Z',
  },
];

// ── Mock setup ───────────────────────────────────────────────────────────────

/** CORS + COEP headers required for cross-origin isolation. */
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Cross-Origin-Resource-Policy': 'cross-origin',
};

function json(data: unknown) {
  return {
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: CORS_HEADERS,
  };
}

/**
 * Set up all API mocks for a test page.
 * Call this in beforeEach to intercept all API and geocoding requests.
 */
export async function setupApiMocks(page: Page): Promise<void> {
  // Backend API — match any host (the base URL varies)
  await page.route('**/lines/nearby/**', (route) =>
    route.fulfill(json(NEARBY_LINES)),
  );

  await page.route('**/directions/', (route) =>
    route.fulfill(json(DIRECTIONS_RESPONSE)),
  );

  await page.route('**/lines/', (route) =>
    route.fulfill(json(LINES)),
  );

  await page.route('**/vote/pending**', (route) =>
    route.fulfill(json(PENDING_LINES)),
  );

  // Order matters: Playwright matches routes in reverse registration order.
  // Register broader patterns first, specific ones last (so they take priority).
  await page.route('**/vote/*', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill(json({ edges_voted: 1, vote: 'approve' }));
    }
    return route.fallback();
  });

  await page.route('**/vote/lines/*', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill(json({ edges_voted: 0, vote: 'approve' }));
    }
    return route.fallback();
  });

  await page.route('**/vote/*/segment**', (route) =>
    route.fulfill(json(VOTEABLE_SEGMENT)),
  );

  await page.route('**/vote/lines/nearby**', (route) =>
    route.fulfill(json(NEARBY_VOTE_LINES)),
  );

  // Fare reports
  await page.route('**/fares/reports', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill(json({
        id: 'fare-001',
        line_id: 'line-101',
        device_id: 'e2e-test-device',
        amount_bob: 2.5,
        created_at: new Date().toISOString(),
      }));
    }
    return route.fallback();
  });

  // Recording sync endpoints
  await page.route('**/recordings/', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill(json({ id: 999, status: 'in_progress', started_at: new Date().toISOString() }));
    }
    return route.fallback();
  });

  await page.route('**/recordings/*/locations/batch', (route) =>
    route.fulfill(json({ added: 10, session_id: 999 })),
  );

  await page.route('**/recordings/*/sensors/batch', (route) =>
    route.fulfill(json({ added: 10, session_id: 999 })),
  );

  await page.route('**/recordings/*/end', (route) =>
    route.fulfill(json({ id: 999, status: 'completed', ended_at: new Date().toISOString() })),
  );

  // Geocoding (Photon — external)
  await page.route('**/photon.komoot.io/api**', (route) => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get('q') ?? '';

    for (const [key, data] of Object.entries(GEOCODING_RESULTS)) {
      if (query.toLowerCase().includes(key.toLowerCase().slice(0, 5))) {
        return route.fulfill(json(data));
      }
    }
    return route.fulfill(json(Object.values(GEOCODING_RESULTS)[0]));
  });

  // Reverse geocoding (Nominatim — external)
  await page.route('**/nominatim.openstreetmap.org/reverse**', (route) =>
    route.fulfill(json(REVERSE_GEOCODE_RESPONSE)),
  );

  // Server reachability check — the app pings the base URL root.
  // Use a narrow pattern so it doesn't intercept actual API endpoints.
  await page.route(/\/\/10\.\d+\.\d+\.\d+:\d+\/?$/, (route) =>
    route.fulfill({ status: 200, body: '', headers: CORS_HEADERS }),
  );
}
