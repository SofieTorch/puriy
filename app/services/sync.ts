/**
 * Sync pending recordings to the server when online.
 */
import NetInfo from '@react-native-community/netinfo';
import api, { isServerReachable } from '@/services/api';
import {
  getPendingSyncRecordings,
  getLocationPoints,
  getSensorReadings,
  getRecording,
  deleteRecording,
} from '@/services/recording-store';

const BATCH_SIZE = 100;
let syncing = false;
const syncListeners = new Set<(value: boolean) => void>();

function setSyncing(value: boolean) {
  syncing = value;
  for (const listener of syncListeners) listener(value);
}

export function subscribeSyncStatus(listener: (value: boolean) => void): () => void {
  syncListeners.add(listener);
  listener(syncing);
  return () => {
    syncListeners.delete(listener);
  };
}

/** Upload one pending recording to the server. Returns true if synced. */
async function syncOneRecording(recordingId: number): Promise<boolean> {
  const rec = getRecording(recordingId);
  if (!rec || rec.status !== 'pending_sync') return false;

  try {
    // 1. Start session on server
    const session = await api.startRecording(
      rec.deviceModel ?? undefined,
      rec.osVersion ?? undefined
    );

    const serverId = session.id;

    // 2. Upload location points in batches
    const points = getLocationPoints(recordingId);
    for (let i = 0; i < points.length; i += BATCH_SIZE) {
      const batch = points.slice(i, i + BATCH_SIZE);
      await api.uploadLocationBatch(serverId, batch);
    }

    // 3. Upload sensor readings in batches
    const readings = getSensorReadings(recordingId);
    for (let i = 0; i < readings.length; i += BATCH_SIZE) {
      const batch = readings.slice(i, i + BATCH_SIZE);
      await api.uploadSensorBatch(serverId, batch);
    }

    // 4. End recording with line
    await api.endRecording(
      serverId,
      rec.lineId,
      rec.lineName,
      (rec.lineType as 'micro' | 'trufi' | 'taxi_trufi' | null) ?? null,
      rec.isDetour ?? false,
      rec.detourReason ?? null,
      rec.detourDescription ?? null,
    );

    // 5. Remove from local DB (data now on server)
    deleteRecording(recordingId);
    return true;
  } catch (err) {
    console.error('Sync failed for recording', recordingId, err);
    return false;
  }
}

/** Sync all pending recordings. Call when network is back. */
export async function syncPendingRecordings(): Promise<number> {
  if (syncing) return 0;

  const netInfo = await NetInfo.fetch();
  if (!netInfo.isConnected) return 0;
  if (!(await isServerReachable())) return 0;

  const pending = getPendingSyncRecordings();
  if (pending.length === 0) return 0;

  setSyncing(true);
  let synced = 0;

  try {
    for (const rec of pending) {
      const ok = await syncOneRecording(rec.id);
      if (ok) synced++;
    }
  } finally {
    setSyncing(false);
  }

  return synced;
}
