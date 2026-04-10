/**
 * Record tab - Start/stop recording transit data.
 */
import * as Location from 'expo-location';
import { Accelerometer, Gyroscope } from 'expo-sensors';

import {
  startBackgroundLocation,
  stopBackgroundLocation,
  onLocationBatch,
  checkLocationPermissions,
  refreshPermissionsAfterSettingsReturn,
} from '@/services/background-location';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  AppState,
  Linking,
  Modal,
  Platform,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import LottieView from 'lottie-react-native';

import { SwipeSwitch } from '@/components/swipe-switch';
import { ThemedView } from '@/components/themed-view';
import { useFocusEffect } from '@react-navigation/native';
import { useTheme } from '@react-navigation/native';
import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import type { SensorReading } from '@/services/api';
import {
  createRecording,
  addSensorReadings,
  finalizeRecording,
  cancelRecording,
  touchRecording,
} from '@/services/recording-store';
import { syncPendingRecordings } from '@/services/sync';
import { setRecordingStatus } from '@/services/recording-status';
import { styles } from '@/styles/record';
import Header from '@/components/header';
import SaveRecordModal from '@/components/save-record-modal';

const SENSOR_INTERVAL = 100;

export default function RecordScreen() {
  const { colors } = useTheme();
  const tabBarHeight = useBottomTabBarHeight();
  const lottieRef = useRef<LottieView>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
  const [locationPermission, setLocationPermission] = useState<boolean>(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [pointsCollected, setPointsCollected] = useState(0);

  // Line selection modal (shown after stopping)
  const [showLineModal, setShowLineModal] = useState(false);

  // Permission modal (shown when location permissions not granted)
  const [showPermissionModal, setShowPermissionModal] = useState(false);

  // Snapshot of stats at the moment recording stopped (so the modal shows stable values)
  const finalDuration = useRef(0);
  const finalPoints = useRef(0);

  const sensorBuffer = useRef<SensorReading[]>([]);
  const accelSubscription = useRef<ReturnType<typeof Accelerometer.addListener> | null>(null);
  const gyroSubscription = useRef<ReturnType<typeof Gyroscope.addListener> | null>(null);
  const durationInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const userWentToSettings = useRef(false);

  const refreshPermissionStatus = useCallback(async () => {
    const { foreground, background } = await checkLocationPermissions();
    const granted = foreground && background;
    setLocationPermission(granted);
    if (!granted) {
      setShowPermissionModal(true);
    } else {
      setShowPermissionModal(false);
    }
  }, []);

  const refreshAfterReturnFromSettings = useCallback(async () => {
    const { foreground, background } = await refreshPermissionsAfterSettingsReturn();
    const granted = foreground && background;
    setLocationPermission(granted);
    setShowPermissionModal(!granted);
    userWentToSettings.current = false;
  }, []);

  useEffect(() => {
    refreshPermissionStatus();
  }, [refreshPermissionStatus]);

  // Re-check when Record tab gains focus
  useFocusEffect(
    useCallback(() => {
      refreshPermissionStatus();
    }, [refreshPermissionStatus])
  );

  // When returning from settings, use request-based refresh (fixes stale get*Async)
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && userWentToSettings.current) {
        timeoutId = setTimeout(() => {
          refreshAfterReturnFromSettings();
          timeoutId = null;
        }, 400);
      }
    });
    return () => {
      sub.remove();
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [refreshAfterReturnFromSettings]);

  // Subscribe to background location updates for points count
  useEffect(() => {
    if (!isRecording) return;
    const unsub = onLocationBatch((count) => {
      setPointsCollected((prev) => prev + count);
    });
    return unsub;
  }, [isRecording]);

  useEffect(() => {
    if (isRecording) {
      lottieRef.current?.play();
      return;
    }

    lottieRef.current?.pause();
    lottieRef.current?.reset();
  }, [isRecording]);

  useEffect(() => {
    setRecordingStatus(isRecording);
  }, [isRecording]);

  useEffect(() => {
    return () => {
      setRecordingStatus(false);
    };
  }, []);

  const handleOpenSettings = () => {
    userWentToSettings.current = true;
    setShowPermissionModal(false);
    Linking.openSettings();
  };

  const startDataCollection = useCallback(async (localRecordingId: number) => {
    // Background location works in both foreground and background
    await startBackgroundLocation();

    Accelerometer.setUpdateInterval(SENSOR_INTERVAL);
    accelSubscription.current = Accelerometer.addListener((data) => {
      const reading: SensorReading = {
        timestamp: new Date().toISOString(),
        accel_x: data.x,
        accel_y: data.y,
        accel_z: data.z,
        gyro_x: null,
        gyro_y: null,
        gyro_z: null,
        pressure: null,
        magnetic_heading: null,
      };
      sensorBuffer.current.push(reading);
      addSensorReadings(localRecordingId, [reading]);
    });

    Gyroscope.setUpdateInterval(SENSOR_INTERVAL);
    gyroSubscription.current = Gyroscope.addListener((data) => {
      const reading: SensorReading = {
        timestamp: new Date().toISOString(),
        accel_x: null,
        accel_y: null,
        accel_z: null,
        gyro_x: data.x,
        gyro_y: data.y,
        gyro_z: data.z,
        pressure: null,
        magnetic_heading: null,
      };
      sensorBuffer.current.push(reading);
      addSensorReadings(localRecordingId, [reading]);
    });

    durationInterval.current = setInterval(() => {
      setRecordingDuration((prev) => prev + 1);
      touchRecording(localRecordingId);
    }, 1000);
  }, []);

  const stopDataCollection = useCallback(() => {
    stopBackgroundLocation();
    if (accelSubscription.current) {
      accelSubscription.current.remove();
      accelSubscription.current = null;
    }
    if (gyroSubscription.current) {
      gyroSubscription.current.remove();
      gyroSubscription.current = null;
    }
    if (durationInterval.current) {
      clearInterval(durationInterval.current);
      durationInterval.current = null;
    }
  }, []);

  const handleRecordingToggle = async (shouldRecord: boolean) => {
    if (shouldRecord) {
      if (!locationPermission) {
        setShowPermissionModal(true);
        return;
      }

      const recording = createRecording({
        deviceModel: Platform.OS,
        osVersion: Platform.Version?.toString(),
      });

      setCurrentSessionId(recording.id);
      setIsRecording(true);
      setRecordingDuration(0);
      setPointsCollected(0);
      sensorBuffer.current = [];

      await startDataCollection(recording.id);
    } else {
      if (!currentSessionId) return;

      stopDataCollection();

      finalDuration.current = recordingDuration;
      finalPoints.current = pointsCollected;

      setIsRecording(false);
      setShowLineModal(true);
    }
  };

  const handleConfirmLine = async ({
    lineId,
    customLineName,
    isDetour,
    detourReason,
    detourDescription,
  }: {
    lineId: string | null;
    customLineName: string | null;
    isDetour: boolean;
    detourReason: string | null;
    detourDescription: string | null;
  }) => {
    if (!currentSessionId) return;
    try {
      finalizeRecording(
        currentSessionId,
        lineId,
        customLineName,
        'pending_sync',
        isDetour,
        detourReason,
        detourDescription,
      );

      const synced = await syncPendingRecordings();

      setShowLineModal(false);
      setCurrentSessionId(null);

      const msg =
        synced > 0
          ? `Recorded ${finalPoints.current} points over ${formatDuration(finalDuration.current)}. Synced to server.`
          : `Recorded ${finalPoints.current} points. Will sync when you're back online.`;
      Alert.alert('Recording Complete', msg);
    } catch (error) {
      console.error('Failed to save recording:', error);
      Alert.alert('Error', 'Failed to save recording.');
    }
  };

  const handleDiscardRecording = () => {
    if (!currentSessionId) return;

    cancelRecording(currentSessionId);

    setShowLineModal(false);
    setCurrentSessionId(null);
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: '#09A6F3' }]}>
      <View style={{ flex: 1, backgroundColor: colors.background }}>
        <Header title="Trayecto" />

        <View style={[styles.content, { paddingBottom: tabBarHeight + 12 }]}>

        {/* Recording Status */}
        {isRecording && (
          <ThemedView style={styles.statusSection}>
            <View style={styles.statusRow}>
              <View style={styles.statusItem}>
                <Text style={styles.statusValue}>{formatDuration(recordingDuration)}</Text>
                <Text style={styles.statusLabel}>Duration</Text>
              </View>
              <View style={styles.statusDivider} />
              <View style={styles.statusItem}>
                <Text style={styles.statusValue}>{pointsCollected}</Text>
                <Text style={styles.statusLabel}>Points</Text>
              </View>
            </View>
            <View style={styles.recordingIndicator}>
              <View style={styles.recordingDot} />
              <Text style={styles.recordingText}>Recording</Text>
            </View>
          </ThemedView>
        )}

        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <LottieView
            ref={lottieRef}
            source={require('../../assets/animations/car_travel.json')}
            loop
            style={{ width: '100%', height: '100%' }}
          />
        </View>

        {/* Swipe Switch */}
        <View style={styles.switchContainer}>
          <SwipeSwitch
            value={isRecording}
            onValueChange={handleRecordingToggle}
            onLabel="Grabando..."
            offLabel="Desliza para empezar"
          />
        </View>
        </View>

        <Modal
          visible={showPermissionModal}
          animationType="fade"
          transparent
          onRequestClose={() => setShowPermissionModal(false)}
        >
          <View className="flex-1 justify-center bg-black/50 px-6">
            <View className="rounded-2xl bg-white p-6">
              <Text className="mb-2 text-xl font-bold text-gray-900">
                Permiso de ubicación
              </Text>
              <Text className="mb-4 text-base leading-6 text-gray-600">
                Para capturar tu recorrido completo mientras usas la app o la tienes en segundo plano (por ejemplo, con la pantalla bloqueada), necesitamos acceso a tu ubicación en todo momento durante la grabación.
              </Text>
              <Text className="mb-6 text-sm leading-5 text-gray-500">
                {Platform.OS === 'ios'
                  ? "A continuación, toca «Ubicación» y elige «Siempre»."
                  : "A continuación, toca «Permisos» y activa «Ubicación» con «Permitir todo el tiempo»."}
              </Text>
              <TouchableOpacity
                className="items-center rounded-xl bg-[#09A6F3] py-3.5"
                onPress={handleOpenSettings}
                activeOpacity={0.8}
              >
                <Text className="text-base font-semibold text-white">Continuar</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        <SaveRecordModal
          visible={showLineModal}
          recordingId={currentSessionId}
          finalDuration={finalDuration.current}
          finalPoints={finalPoints.current}
          formatDuration={formatDuration}
          onDiscard={handleDiscardRecording}
          onConfirm={handleConfirmLine}
        />
      </View>
    </SafeAreaView>
  );
}

