let recording = false;
const recordingListeners = new Set<(value: boolean) => void>();

function notify() {
  for (const listener of recordingListeners) listener(recording);
}

export function setRecordingStatus(value: boolean): void {
  recording = value;
  notify();
}

export function subscribeRecordingStatus(listener: (value: boolean) => void): () => void {
  recordingListeners.add(listener);
  listener(recording);
  return () => {
    recordingListeners.delete(listener);
  };
}
