import { sql } from 'drizzle-orm';
import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

/** Cached lines from the server (refreshed when online). */
export const lines = sqliteTable('lines', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  description: text('description'),
  status: text('status', { enum: ['pending', 'approved', 'rejected', 'merged'] }).notNull(),
  createdAt: text('created_at').notNull(),
  updatedAt: text('updated_at').notNull(),
  cachedAt: text('cached_at').notNull(),
});

/** Local recording sessions. serverId is set after sync. */
export const recordings = sqliteTable('recordings', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  serverId: integer('server_id'), // Set after synced to server
  status: text('status', {
    enum: ['in_progress', 'pending_sync', 'synced', 'discarded', 'cancelled'],
  }).notNull(),
  lineId: text('line_id'), // Server line ID (UUID, if existing line selected)
  lineName: text('line_name'), // New line name (if creating)
  lineType: text('line_type'), // Bus type for a new line: micro | trufi | taxi_trufi
  isDetour: integer('is_detour', { mode: 'boolean' }).default(false),
  detourReason: text('detour_reason'),
  detourDescription: text('detour_description'),
  direction: text('direction'),
  deviceModel: text('device_model'),
  osVersion: text('os_version'),
  notes: text('notes'),
  startedAt: text('started_at').notNull(),
  endedAt: text('ended_at'),
  lastActivityAt: text('last_activity_at').notNull(),
  syncedAt: text('synced_at'), // When fully synced to server
  createdAt: text('created_at').notNull(),
});

/** Location points for a recording. */
export const locationPoints = sqliteTable('location_points', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  recordingId: integer('recording_id').notNull().references(() => recordings.id, { onDelete: 'cascade' }),
  timestamp: text('timestamp').notNull(),
  latitude: real('latitude').notNull(),
  longitude: real('longitude').notNull(),
  altitude: real('altitude'),
  speed: real('speed'),
  bearing: real('bearing'),
  horizontalAccuracy: real('horizontal_accuracy'),
  verticalAccuracy: real('vertical_accuracy'),
});

/** Sensor readings for a recording. */
export const sensorReadings = sqliteTable('sensor_readings', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  recordingId: integer('recording_id').notNull().references(() => recordings.id, { onDelete: 'cascade' }),
  timestamp: text('timestamp').notNull(),
  accelX: real('accel_x'),
  accelY: real('accel_y'),
  accelZ: real('accel_z'),
  gyroX: real('gyro_x'),
  gyroY: real('gyro_y'),
  gyroZ: real('gyro_z'),
  pressure: real('pressure'),
  magneticHeading: real('magnetic_heading'),
});

export type Line = typeof lines.$inferSelect;
export type NewLine = typeof lines.$inferInsert;
export type Recording = typeof recordings.$inferSelect;
export type NewRecording = typeof recordings.$inferInsert;
export type LocationPoint = typeof locationPoints.$inferSelect;
export type NewLocationPoint = typeof locationPoints.$inferInsert;
export type SensorReading = typeof sensorReadings.$inferSelect;
export type NewSensorReading = typeof sensorReadings.$inferInsert;

/** Key-value preferences store. */
export const preferences = sqliteTable('preferences', {
  key: text('key').primaryKey(),
  value: text('value').notNull(),
  updatedAt: text('updated_at').default(sql`(datetime('now'))`),
});

export type Preference = typeof preferences.$inferSelect;

/** Saved trips (favorites). */
export const savedTrips = sqliteTable('saved_trips', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  originName: text('origin_name').notNull(),
  destName: text('dest_name').notNull(),
  originLon: real('origin_lon').notNull(),
  originLat: real('origin_lat').notNull(),
  destLon: real('dest_lon').notNull(),
  destLat: real('dest_lat').notNull(),
  type: text('type', { enum: ['one_time', 'commute'] }).notNull(),
  routeJson: text('route_json').notNull(), // serialized DirectionsResponse
  /** Optional HH:mm in local Cochabamba time. When set, a local notification
   * is scheduled to fire LEAD_MINUTES_BEFORE before this time. */
  departureTime: text('departure_time'),
  createdAt: text('created_at').notNull().default(sql`(datetime('now'))`),
});

export type SavedTrip = typeof savedTrips.$inferSelect;
export type NewSavedTrip = typeof savedTrips.$inferInsert;

/** Recent search locations for autocomplete history. */
export const searchHistory = sqliteTable('search_history', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  lon: real('lon').notNull(),
  lat: real('lat').notNull(),
  usedAt: text('used_at').notNull().default(sql`(datetime('now'))`),
});

export type SearchHistoryEntry = typeof searchHistory.$inferSelect;
