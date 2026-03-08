/**
 * API client for the Open Transit backend.
 */

// Update this to your server URL
// const API_BASE_URL = __DEV__ 
//   ? 'http://localhost:8000'  // Development
//   : 'https://api.yourdomain.com';  // Production

// const API_BASE_URL = 'https://movility-cbba-ndkpt.ondigitalocean.app';
export const API_BASE_URL = 'http://172.28.41.230:8000';
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
  id: number;
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
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
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
    lineId: number | null,
    lineName: string | null
  ): Promise<RecordingSession> {
    return this.request<RecordingSession>(`/recordings/${sessionId}/end`, {
      method: 'POST',
      body: JSON.stringify({
        line_id: lineId,
        line_name: lineName,
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
}

export const api = new ApiClient();
export default api;
