/**
 * Modal for saving a planned route — captures the trip type
 * (one-time vs commute) and an optional departure time HH:mm.
 *
 * The departure time, when provided, drives a local notification
 * scheduled by `services/trip-notifications.ts` (CU-04 / RF-32 /
 * CU-14 / RF-36).
 */
import React, { useEffect, useState } from 'react';
import {
  Modal,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import type { TripType } from '@/services/saved-trips';

const BLUE = '#09A6F3';

export interface SaveTripModalResult {
  type: TripType;
  /** "HH:mm" 24h local Cochabamba time, or null. */
  departureTime: string | null;
}

interface SaveTripModalProps {
  visible: boolean;
  onCancel(): void;
  onSave(result: SaveTripModalResult): void;
}

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

function isValidTime(value: string): boolean {
  return TIME_PATTERN.test(value.trim());
}

export function SaveTripModal({
  visible,
  onCancel,
  onSave,
}: SaveTripModalProps): React.ReactElement {
  const [type, setType] = useState<TripType>('one_time');
  const [time, setTime] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) {
      setType('one_time');
      setTime('');
      setError(null);
    }
  }, [visible]);

  function handleSave(): void {
    const trimmed = time.trim();
    if (trimmed && !isValidTime(trimmed)) {
      setError('Formato HH:mm (ej. 07:30)');
      return;
    }
    onSave({ type, departureTime: trimmed || null });
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View
        className="flex-1 items-center justify-center bg-black/50 px-6"
        accessible={false}
      >
        <View className="w-full max-w-md rounded-2xl bg-white p-5">
          <View className="mb-4 flex-row items-center justify-between">
            <Text className="text-lg font-bold text-gray-800">
              Guardar ruta
            </Text>
            <Pressable onPress={onCancel} testID="save-trip-cancel">
              <Feather name="x" size={20} color="#6B7280" />
            </Pressable>
          </View>

          <Text className="mb-2 text-sm font-semibold text-gray-700">
            Tipo de viaje
          </Text>
          <View className="mb-4 flex-row gap-2">
            <Pressable
              testID="save-trip-type-one_time"
              onPress={() => setType('one_time')}
              className={`flex-1 rounded-lg border px-4 py-3 ${
                type === 'one_time'
                  ? 'border-[#09A6F3] bg-[#DDF6FF]'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <Text
                className={`text-center text-sm font-semibold ${
                  type === 'one_time' ? 'text-[#09A6F3]' : 'text-gray-600'
                }`}
              >
                Solo por hoy
              </Text>
            </Pressable>
            <Pressable
              testID="save-trip-type-commute"
              onPress={() => setType('commute')}
              className={`flex-1 rounded-lg border px-4 py-3 ${
                type === 'commute'
                  ? 'border-[#09A6F3] bg-[#DDF6FF]'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <Text
                className={`text-center text-sm font-semibold ${
                  type === 'commute' ? 'text-[#09A6F3]' : 'text-gray-600'
                }`}
              >
                Viaje recurrente
              </Text>
            </Pressable>
          </View>

          <Text className="mb-2 text-sm font-semibold text-gray-700">
            Hora de salida{' '}
            <Text className="font-normal text-gray-400">(opcional)</Text>
          </Text>
          <TextInput
            testID="save-trip-time"
            value={time}
            onChangeText={(t) => {
              setTime(t);
              if (error) setError(null);
            }}
            placeholder="HH:mm (ej. 07:30)"
            keyboardType="numbers-and-punctuation"
            maxLength={5}
            className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 text-base"
          />
          <Text className="mt-1 text-xs text-gray-400">
            Si la indicas, te avisaremos 10 minutos antes con cualquier
            desvío activo en la línea.
          </Text>
          {error && (
            <Text className="mt-1 text-xs text-red-500" testID="save-trip-error">
              {error}
            </Text>
          )}

          <View className="mt-5 flex-row gap-2">
            <Pressable
              onPress={onCancel}
              className="flex-1 rounded-lg border border-gray-200 px-4 py-3"
            >
              <Text className="text-center text-sm font-semibold text-gray-600">
                Cancelar
              </Text>
            </Pressable>
            <Pressable
              testID="save-trip-confirm"
              onPress={handleSave}
              style={{ backgroundColor: BLUE }}
              className="flex-1 rounded-lg px-4 py-3"
            >
              <Text className="text-center text-sm font-semibold text-white">
                Guardar
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}
