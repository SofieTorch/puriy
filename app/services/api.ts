/**
 * API client for the Open Transit backend.
 * API_BASE_URL is configurable via environment variable (for E2E tests):
 *   API_BASE_URL=http://localhost:8001 npx expo start
 */

import Constants from 'expo-constants';

export const API_BASE_URL =
  Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://172.27.25.135:8000';
const SERVER_CHECK_TIMEOUT_MS = 3000;

/** True when the backend host responds (any HTTP status). */
export async function isServerReachable(): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SERVER_CHECK_TIMEOUT_MS);

  try {
    await fetch(API_BASE_URL, { signal: controller.signal });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

export interface Line {
  id: string;
  name: string;
  description: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'merged';
  created_at: string;
  updated_at: string;
}

export interface RecordingSession {
  id: number;
  line_id: number | null;
  direction: string | null;
  device_model: string | null;
  os_version: string | null;
  notes: string | null;
  status: 'in_progress' | 'completed' | 'cancelled' | 'abandoned' | 'discarded';
  started_at: string;
  ended_at: string | null;
  last_activity_at: string;
  computed_path: number[][] | null;
}

export interface LocationPoint {
  timestamp: string;
  latitude: number;
  longitude: number;
  altitude: number | null;
  speed: number | null;
  bearing: number | null;
  horizontal_accuracy: number | null;
  vertical_accuracy: number | null;
}

export interface SensorReading {
  timestamp: string;
  accel_x: number | null;
  accel_y: number | null;
  accel_z: number | null;
  gyro_x: number | null;
  gyro_y: number | null;
  gyro_z: number | null;
  pressure: number | null;
  magnetic_heading: number | null;
}

export interface PendingLine {
  line_id: string;
  line_name: string;
  line_description: string | null;
  route_id: string;
  pending_edge_count: number;
  total_edge_count: number;
}

export interface VoteableEdge {
  id: string;
  sequence: number;
  valhalla_edge_id: number | null;
  path: number[][] | null;
  confidence: number;
  votes_for: number;
  votes_against: number;
}

export interface VoteableSection {
  section_index: number;
  edges: VoteableEdge[];
  trip_count: number;
  geometry: number[][];
}

export interface VoteableSegment {
  route_id: string;
  line_name: string;
  line_description: string | null;
  route_geojson: { geometry?: { coordinates?: number[][] } } | null;
  sections: VoteableSection[];
  edges: VoteableEdge[];
  segment_geojson: object | null;
}

export interface VoteResponse {
  edges_voted: number;
  vote: 'approve' | 'reject';
}

export interface DirectionsLeg {
  mode: 'bus' | 'walk';
  line_name: string | null;
  line_id: string | null;
  geometry: [number, number][];
  distance_m: number;
  duration_s: number;
  fare_bob?: number | null;        // RF-03 — bus legs only
  frequency_min?: number | null;   // RF-04 — bus legs only
  detour_alert?: DetourAlert | null;
}

export interface DirectionsResponse {
  legs: DirectionsLeg[];
  total_distance_m: number;
  total_duration_s: number;
  total_fare_bob?: number | null;  // RF-30 — sum across bus legs
}

export interface RamalSummary {
  route_id: string;
  endpoint_zones: (string | null)[];
  street_summary: string[];
}

export interface RamalDescriptor {
  id: string;
  route_id: string;
  text: string;
  votes_count: number;
  created_at: string;
  voted_by_me: boolean;
}

export interface NearbyLineWithRoute {
  line_id: string;
  line_name: string;
  line_description: string | null;
  route_geojson: { type: string; coordinates: [number, number][] } | null;
  detour_alert?: DetourAlert | null;
  ramales: RamalSummary[];
}

export interface NearbyLine {
  line_id: string;
  line_name: string;
  line_description: string | null;
}

export interface DetourAlert {
  active: boolean;
  detour_id: string;
  reason: string | null;
  description: string | null;
  days_since_confirmed: number;
  confidence_pct: number;
  detour_path?: [number, number][] | null;
  diverges_at?: string | null;
  rejoins_at?: string | null;
}

export interface DetourInfo {
  id: string;
  line_id: string;
  line_name: string;
  reason: string | null;
  description: string | null;
  days_since_confirmed: number;
  confidence_pct: number;
}

export interface CommonAmount {
  amount_bob: number;
  report_count: number;
}

export interface ZoneFare {
  boarding_zone: string;
  alighting_zone: string;
  amount_bob: number;
  report_count: number;
}

export interface LineFare {
  line_id: string;
  line_name: string;
  line_type: 'micro' | 'trufi' | 'taxi_trufi' | null;
  flat_rate: number | null;
  zone_fares: ZoneFare[];
  common_amounts: CommonAmount[];
}

/** Carries the response status + parsed body so callers can branch
 * on specific error shapes (e.g. 409 with `detail.existing` for the
 * descriptor create flow). */
export class ApiError extends Error {
  status: number;
  body: any;
  constructor(message: string, status: number, body: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    // Attach the device id on every request as `X-Device-Id`. This is
    // the canonical way for the server to know who's calling — the
    // older pattern of repeating `device_id` in every body / query
    // string is preserved for now for endpoints that consume it
    // explicitly, but new endpoints (and `start_recording`) read from
    // the header so a missed-parameter bug like the one in v1 can't
    // recur. Imported lazily to avoid touching the local DB before
    // DatabaseProvider has mounted (some module-level callers race).
    const { getDeviceId } = require('@/services/device-id');
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-Device-Id': getDeviceId(),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const message = typeof error.detail === 'string'
        ? error.detail
        : (error.detail?.message ?? `API error: ${response.status}`);
      throw new ApiError(message, response.status, error);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  }

  // ============================================================
  // Lines
  // ============================================================

  async getLines(status?: string): Promise<Line[]> {
    const params = status ? `?status=${status}` : '';
    return this.request<Line[]>(`/lines/${params}`);
  }

  async getLine(lineId: number): Promise<Line> {
    return this.request<Line>(`/lines/${lineId}`);
  }

  // ============================================================
  // Recording Sessions
  // ============================================================

  async startRecording(
    deviceModel?: string,
    osVersion?: string
  ): Promise<RecordingSession> {
    // device_id is read from the `X-Device-Id` header by the server
    // (see `request()` above) — no need to thread it through here.
    return this.request<RecordingSession>('/recordings/', {
      method: 'POST',
      body: JSON.stringify({
        device_model: deviceModel,
        os_version: osVersion,
      }),
    });
  }

  async endRecording(
    sessionId: number,
    lineId: string | null,
    lineName: string | null,
    isDetour: boolean = false,
    detourReason: string | null = null,
    detourDescription: string | null = null,
  ): Promise<RecordingSession> {
    return this.request<RecordingSession>(`/recordings/${sessionId}/end`, {
      method: 'POST',
      body: JSON.stringify({
        line_id: lineId,
        line_name: lineName,
        is_detour: isDetour,
        detour_reason: detourReason,
        detour_description: detourDescription,
      }),
    });
  }

  async cancelRecording(sessionId: number): Promise<RecordingSession> {
    return this.request<RecordingSession>(`/recordings/${sessionId}/cancel`, {
      method: 'POST',
    });
  }

  async getRecording(sessionId: number): Promise<RecordingSession> {
    return this.request<RecordingSession>(`/recordings/${sessionId}`);
  }

  async getRecordings(userId?: number): Promise<RecordingSession[]> {
    const params = userId ? `?user_id=${userId}` : '';
    return this.request<RecordingSession[]>(`/recordings/${params}`);
  }

  // ============================================================
  // Location Points (Batch Upload)
  // ============================================================

  async uploadLocationBatch(
    sessionId: number,
    points: LocationPoint[]
  ): Promise<{ added: number; session_id: number }> {
    return this.request(`/recordings/${sessionId}/locations/batch`, {
      method: 'POST',
      body: JSON.stringify({ points }),
    });
  }

  // ============================================================
  // Sensor Readings (Batch Upload)
  // ============================================================

  async uploadSensorBatch(
    sessionId: number,
    readings: SensorReading[]
  ): Promise<{ added: number; session_id: number }> {
    return this.request(`/recordings/${sessionId}/sensors/batch`, {
      method: 'POST',
      body: JSON.stringify({ readings }),
    });
  }
  // ============================================================
  // Voting
  // ============================================================

  async getPendingVotes(deviceId: string): Promise<PendingLine[]> {
    return this.request<PendingLine[]>(
      `/vote/pending?device_id=${encodeURIComponent(deviceId)}`
    );
  }

  async getVoteableSegment(
    lineId: string,
    deviceId: string
  ): Promise<VoteableSegment> {
    return this.request<VoteableSegment>(
      `/vote/${lineId}/segment?device_id=${encodeURIComponent(deviceId)}`
    );
  }

  async submitVote(
    lineId: string,
    deviceId: string,
    vote: 'approve' | 'reject',
    sectionIndex?: number,
  ): Promise<VoteResponse> {
    const body: Record<string, unknown> = { device_id: deviceId, vote };
    if (sectionIndex !== undefined) body.section_index = sectionIndex;
    return this.request<VoteResponse>(`/vote/${lineId}`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // ============================================================
  // Line Route
  // ============================================================

  // ============================================================
  // Nearby Lines (by coordinate)
  // ============================================================

  async getNearbyLinesByLocation(
    lon: number,
    lat: number,
    radiusMeters: number = 500,
    includePending: boolean = false
  ): Promise<NearbyLineWithRoute[]> {
    return this.request<NearbyLineWithRoute[]>(
      `/lines/nearby/?longitude=${lon}&latitude=${lat}&radius_meters=${radiusMeters}&include_pending=${includePending}`
    );
  }

  // ============================================================
  // Directions
  // ============================================================

  async getDirections(
    origin: [number, number],
    destination: [number, number],
    pendingLines: boolean = false,
    pendingRoutes: boolean = false
  ): Promise<DirectionsResponse> {
    return this.request<DirectionsResponse>('/directions/', {
      method: 'POST',
      body: JSON.stringify({
        origin,
        destination,
        include_pending_lines: pendingLines,
        include_pending_routes: pendingRoutes,
      }),
    });
  }

  // ============================================================
  // Line Familiarity Voting
  // ============================================================

  async getNearbyLines(deviceId: string): Promise<NearbyLine[]> {
    return this.request<NearbyLine[]>(
      `/vote/lines/nearby?device_id=${encodeURIComponent(deviceId)}`
    );
  }

  async submitLineVote(
    lineId: string,
    deviceId: string,
    vote: 'approve' | 'reject'
  ): Promise<void> {
    await this.request(`/vote/lines/${lineId}`, {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId, vote }),
    });
  }

  // ============================================================
  // Detours
  // ============================================================

  async getActiveDetour(lineId: string): Promise<DetourInfo | null> {
    try {
      return await this.request<DetourInfo>(`/detours/active/${lineId}`);
    } catch {
      return null;
    }
  }

  async confirmDetour(detourId: string): Promise<void> {
    await this.request(`/detours/${detourId}/confirm`, { method: 'POST' });
  }

  // ============================================================
  // Fares
  // ============================================================

  /** Preview which fare zones (= municipalities) the system would
   * identify for a pair of GPS points, without persisting anything.
   * Used to show users the identified municipalities before they
   * confirm a fare report (CU-08 transparency). */
  async resolveFareZones(params: {
    boardingLat: number;
    boardingLon: number;
    alightingLat: number;
    alightingLon: number;
  }): Promise<{ boarding_zone: string | null; alighting_zone: string | null }> {
    return this.request('/fares/zones/resolve', {
      method: 'POST',
      body: JSON.stringify({
        boarding_latitude: params.boardingLat,
        boarding_longitude: params.boardingLon,
        alighting_latitude: params.alightingLat,
        alighting_longitude: params.alightingLon,
      }),
    });
  }

  async submitFareReport(params: {
    lineId: string;
    deviceId: string;
    amountBob: number;
    boardingLat: number;
    boardingLon: number;
    alightingLat: number;
    alightingLon: number;
    /** 'registration' for free entry, 'confirmation' when picking an existing chip. */
    source?: 'registration' | 'confirmation';
  }): Promise<void> {
    await this.request('/fares/reports', {
      method: 'POST',
      body: JSON.stringify({
        line_id: params.lineId,
        device_id: params.deviceId,
        amount_bob: params.amountBob,
        boarding_latitude: params.boardingLat,
        boarding_longitude: params.boardingLon,
        alighting_latitude: params.alightingLat,
        alighting_longitude: params.alightingLon,
        source: params.source ?? 'registration',
      }),
    });
  }

  /**
   * Aggregated fare summary for one line — flat rate (micros) or zone-pair
   * matrix (trufis), plus the most-reported individual amounts to render
   * as "tap to confirm" chips in the save-record modal.
   */
  async getLineFares(lineId: string): Promise<LineFare> {
    return this.request<LineFare>(`/fares/lines/${encodeURIComponent(lineId)}`);
  }

  // ============================================================
  // Devices & subscriptions (push notifications)
  // ============================================================

  /**
   * Upsert this device on the server. Called on every app launch — even
   * when the user denied notification permission, in which case `expoToken`
   * is null but the device row is still created so any subsequent write
   * keyed by `device_id` (recordings, votes, fares) satisfies its FK.
   */
  async registerDevice(params: {
    deviceId: string;
    expoToken: string | null;
    platform: 'ios' | 'android';
    locale?: string | null;
  }): Promise<void> {
    await this.request('/devices/register', {
      method: 'POST',
      body: JSON.stringify({
        device_id: params.deviceId,
        expo_push_token: params.expoToken,
        platform: params.platform,
        locale: params.locale ?? null,
      }),
    });
  }

  /** Replace the device's commute subscriptions with `lineIds`. */
  async replaceCommuteSubscriptions(deviceId: string, lineIds: string[]): Promise<void> {
    await this.request(`/devices/${encodeURIComponent(deviceId)}/subscriptions`, {
      method: 'PUT',
      body: JSON.stringify({ line_ids: lineIds }),
    });
  }

  /** Remove a single commute subscription. No-op if it didn't exist. */
  async deleteCommuteSubscription(deviceId: string, lineId: string): Promise<void> {
    await this.request(
      `/devices/${encodeURIComponent(deviceId)}/subscriptions/${encodeURIComponent(lineId)}`,
      { method: 'DELETE' },
    );
  }

  /** Returns the GeoJSON FeatureCollection of all active ramales for
   * a line — one Feature per ramal with `route_id`, `ramal_label`,
   * `endpoint_zones`, and `street_summary` in `properties`. */
  async getLineRoute(lineId: string): Promise<{
    type: 'FeatureCollection';
    features: Array<{
      type: 'Feature';
      properties: {
        line_id: string;
        line_name: string;
        route_id: string;
        ramal_label: string;
        street_summary: string[];
        endpoint_zones: (string | null)[];
        fragment_index: number;
        fragment_count: number;
      };
      geometry: { type: 'LineString'; coordinates: number[][] };
    }>;
  }> {
    return this.request(`/lines/${encodeURIComponent(lineId)}/route`);
  }

  // ============================================================
  // Ramal descriptors (gap #7)
  // ============================================================

  /** List existing descriptors for a route, ordered by votes desc.
   * `voted_by_me` reflects the supplied `deviceId`. */
  async getRamalDescriptors(routeId: string, deviceId: string): Promise<RamalDescriptor[]> {
    return this.request<RamalDescriptor[]>(
      `/routes/${encodeURIComponent(routeId)}/descriptors/?device_id=${encodeURIComponent(deviceId)}`,
    );
  }

  /** Idempotent upvote — server returns the descriptor with `voted_by_me=true`. */
  async upvoteRamalDescriptor(
    routeId: string, descriptorId: string, deviceId: string,
  ): Promise<RamalDescriptor> {
    return this.request<RamalDescriptor>(
      `/routes/${encodeURIComponent(routeId)}/descriptors/${encodeURIComponent(descriptorId)}/upvote`,
      { method: 'POST', body: JSON.stringify({ device_id: deviceId }) },
    );
  }

  /** Reverse an upvote. */
  async unvoteRamalDescriptor(
    routeId: string, descriptorId: string, deviceId: string,
  ): Promise<RamalDescriptor> {
    return this.request<RamalDescriptor>(
      `/routes/${encodeURIComponent(routeId)}/descriptors/${encodeURIComponent(descriptorId)}/upvote`,
      { method: 'DELETE', body: JSON.stringify({ device_id: deviceId }) },
    );
  }

  /** Create a new descriptor. Throws with `existing` payload (HTTP 409)
   * when a descriptor with the same normalised text already exists for
   * the route — caller should fall back to upvoting it. */
  async createRamalDescriptor(
    routeId: string, text: string, deviceId: string,
  ): Promise<RamalDescriptor> {
    return this.request<RamalDescriptor>(
      `/routes/${encodeURIComponent(routeId)}/descriptors/`,
      { method: 'POST', body: JSON.stringify({ text, device_id: deviceId }) },
    );
  }
}

export const api = new ApiClient();
export default api;
