/**
 * Local recording store - CRUD for offline recordings.
 */
import { asc, eq } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import {
  recordings as recordingsTable,
  locationPoints as locationPointsTable,
  sensorReadings as sensorReadingsTable,
  type NewRecording,
  type NewLocationPoint,
  type NewSensorReading,
  type Recording,
} from '@/db/schema';
import type { LocationPoint as ApiLocationPoint } from '@/services/api';
import type { SensorReading as ApiSensorReading } from '@/services/api';

/** Create a new local recording (in_progress). */
export function createRecording(opts: {
  direction?: string;
  deviceModel?: string;
  osVersion?: string;
}): Recording {
  const now = new Date().toISOString();
  const [row] = getDb()
    .insert(recordingsTable)
    .values({
      status: 'in_progress',
      direction: opts.direction,
      deviceModel: opts.deviceModel,
      osVersion: opts.osVersion,
      startedAt: now,
      lastActivityAt: now,
      createdAt: now,
    })
    .returning()
    .all();

  return row!;
}

/** Add location points to a recording. */
export function addLocationPoints(
  recordingId: number,
  points: ApiLocationPoint[]
): void {
  for (const p of points) {
    getDb().insert(locationPointsTable)
      .values({
        recordingId,
        timestamp: p.timestamp,
        latitude: p.latitude,
        longitude: p.longitude,
        altitude: p.altitude ?? null,
        speed: p.speed ?? null,
        bearing: p.bearing ?? null,
        horizontalAccuracy: p.horizontal_accuracy ?? null,
        verticalAccuracy: p.vertical_accuracy ?? null,
      })
      .run();
  }
}

/** Add sensor readings to a recording. */
export function addSensorReadings(
  recordingId: number,
  readings: ApiSensorReading[]
): void {
  for (const r of readings) {
    getDb().insert(sensorReadingsTable).values({
      recordingId,
      timestamp: r.timestamp,
      accelX: r.accel_x ?? null,
      accelY: r.accel_y ?? null,
      accelZ: r.accel_z ?? null,
      gyroX: r.gyro_x ?? null,
      gyroY: r.gyro_y ?? null,
      gyroZ: r.gyro_z ?? null,
      pressure: r.pressure ?? null,
      magneticHeading: r.magnetic_heading ?? null,
    }).run();
  }
}

/** Finalize recording with line selection (pending_sync or discarded). */
export function finalizeRecording(
  recordingId: number,
  lineId: string | null,
  lineName: string | null,
  status: 'pending_sync' | 'discarded',
  isDetour: boolean = false,
  detourReason: string | null = null,
  detourDescription: string | null = null,
): void {
  const now = new Date().toISOString();
  getDb().update(recordingsTable)
    .set({
      status,
      lineId,
      lineName,
      isDetour,
      detourReason,
      detourDescription,
      endedAt: now,
      lastActivityAt: now,
    })
    .where(eq(recordingsTable.id, recordingId))
    .run();
}

/** Mark recording as cancelled. */
export function cancelRecording(recordingId: number): void {
  const now = new Date().toISOString();
  getDb().update(recordingsTable)
    .set({
      status: 'cancelled',
      endedAt: now,
    })
    .where(eq(recordingsTable.id, recordingId))
    .run();
}

/** Get in-progress recording (should be at most one). */
export function getInProgressRecording(): Recording | undefined {
  const rows = getDb()
    .select()
    .from(recordingsTable)
    .where(eq(recordingsTable.status, 'in_progress'))
    .limit(1)
    .all();

  return rows[0];
}

/** Get recording by id. */
export function getRecording(recordingId: number): Recording | undefined {
  return getDb().select().from(recordingsTable).where(eq(recordingsTable.id, recordingId)).get();
}

/** Get pending sync recordings (for upload). */
export function getPendingSyncRecordings(): Recording[] {
  return getDb()
    .select()
    .from(recordingsTable)
    .where(eq(recordingsTable.status, 'pending_sync'))
    .all();
}

/** Get location points for a recording. */
export function getLocationPoints(recordingId: number): ApiLocationPoint[] {
  const rows = getDb()
    .select()
    .from(locationPointsTable)
    .where(eq(locationPointsTable.recordingId, recordingId))
    .orderBy(asc(locationPointsTable.timestamp))
    .all();

  return rows.map((r) => ({
    timestamp: r.timestamp,
    latitude: r.latitude,
    longitude: r.longitude,
    altitude: r.altitude,
    speed: r.speed,
    bearing: r.bearing,
    horizontal_accuracy: r.horizontalAccuracy,
    vertical_accuracy: r.verticalAccuracy,
  }));
}

/** Get sensor readings for a recording. */
export function getSensorReadings(recordingId: number): ApiSensorReading[] {
  const rows = getDb()
    .select()
    .from(sensorReadingsTable)
    .where(eq(sensorReadingsTable.recordingId, recordingId))
    .orderBy(asc(sensorReadingsTable.timestamp))
    .all();

  return rows.map((r) => ({
    timestamp: r.timestamp,
    accel_x: r.accelX,
    accel_y: r.accelY,
    accel_z: r.accelZ,
    gyro_x: r.gyroX,
    gyro_y: r.gyroY,
    gyro_z: r.gyroZ,
    pressure: r.pressure,
    magnetic_heading: r.magneticHeading,
  }));
}

/** Delete a recording and its points/readings (e.g. after successful sync). */
export function deleteRecording(recordingId: number): void {
  getDb().delete(locationPointsTable).where(eq(locationPointsTable.recordingId, recordingId)).run();
  getDb().delete(sensorReadingsTable).where(eq(sensorReadingsTable.recordingId, recordingId)).run();
  getDb().delete(recordingsTable).where(eq(recordingsTable.id, recordingId)).run();
}

/** Update last activity timestamp. */
export function touchRecording(recordingId: number): void {
  const now = new Date().toISOString();
  getDb().update(recordingsTable)
    .set({ lastActivityAt: now })
    .where(eq(recordingsTable.id, recordingId))
    .run();
}
