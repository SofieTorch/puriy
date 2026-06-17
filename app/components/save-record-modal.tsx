import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, Switch, Text, TextInput, TouchableOpacity, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';

import type { CommonAmount, DetourInfo, Line, LineFare } from '@/services/api';
import api from '@/services/api';
import { getLines } from '@/services/line-cache';
import { getDeviceId } from '@/services/device-id';
import RouteMap from '@/components/route-map';
import { getDb } from '@/lib/db';
import { locationPoints } from '@/db/schema';
import { eq, asc, desc } from 'drizzle-orm';

const DETOUR_REASONS = ['Construcción', 'Protesta', 'Accidente', 'Otro'] as const;
type DetourReason = (typeof DETOUR_REASONS)[number];

type SaveRecordModalProps = {
  visible: boolean;
  recordingId: number | null;
  finalDuration: number;
  finalPoints: number;
  formatDuration: (seconds: number) => string;
  onDiscard: () => void;
  onConfirm: (selection: {
    lineId: string | null;
    customLineName: string | null;
    isDetour: boolean;
    detourReason: string | null;
    detourDescription: string | null;
  }) => Promise<void>;
};

export default function SaveRecordModal({
  visible,
  recordingId,
  finalDuration,
  finalPoints,
  formatDuration,
  onDiscard,
  onConfirm,
}: SaveRecordModalProps) {
  const [lines, setLines] = useState<Line[]>([]);
  const [selectedLine, setSelectedLine] = useState<Line | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [customLineName, setCustomLineName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const [fareAmount, setFareAmount] = useState('');
  const [fareOptions, setFareOptions] = useState<CommonAmount[]>([]);
  /** Tracks how the user supplied `fareAmount`: 'chip' = picked an existing
   * option (becomes a CONFIRMATION on the server), 'free' = typed into the
   * input (becomes a REGISTRATION). */
  const [fareSource, setFareSource] = useState<'chip' | 'free'>('free');

  const [isDetour, setIsDetour] = useState(false);
  const [detourReason, setDetourReason] = useState<DetourReason | null>(null);
  const [detourDescription, setDetourDescription] = useState('');
  const [activeDetour, setActiveDetour] = useState<DetourInfo | null>(null);
  const [detourPromptDismissed, setDetourPromptDismissed] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [recordedPath, setRecordedPath] = useState<[number, number][]>([]);
  const [lineRouteCoords, setLineRouteCoords] = useState<[number, number][]>([]);
  // Identified municipalities for the fare report (CU-08 transparency).
  // null = not yet resolved; values inside may also be null when the
  // GPS point falls outside any defined fare zone.
  const [identifiedZones, setIdentifiedZones] = useState<{
    boarding: string | null; alighting: string | null;
  } | null>(null);

  useEffect(() => {
    if (!visible) return;

    let mounted = true;
    const fetchLines = async () => {
      try {
        const data = await getLines();
        if (mounted) setLines(data);
      } catch {
        if (mounted) setLines([]);
      }
    };

    setSelectedLine(null);
    setDropdownOpen(false);
    setCustomLineName('');
    setFareAmount('');
    setIsSaving(false);
    setIsDetour(false);
    setDetourReason(null);
    setDetourDescription('');
    setActiveDetour(null);
    setDetourPromptDismissed(false);
    setShowConfirmation(false);
    setRecordedPath([]);
    setLineRouteCoords([]);
    setIdentifiedZones(null);
    fetchLines();

    return () => { mounted = false; };
  }, [visible]);

  useEffect(() => {
    if (!selectedLine) {
      setActiveDetour(null);
      setDetourPromptDismissed(false);
      return;
    }
    let mounted = true;
    api.getActiveDetour(selectedLine.id.toString()).then((detour) => {
      if (mounted) { setActiveDetour(detour); setDetourPromptDismissed(false); }
    });
    return () => { mounted = false; };
  }, [selectedLine]);

  // Fare options to confirm — fetched whenever a line is picked. We
  // ignore failures (best-effort): the user can still type freely.
  useEffect(() => {
    if (!selectedLine) {
      setFareOptions([]);
      return;
    }
    let mounted = true;
    api
      .getLineFares(selectedLine.id.toString())
      .then((data: LineFare) => {
        if (mounted) setFareOptions(data.common_amounts);
      })
      .catch(() => {
        if (mounted) setFareOptions([]);
      });
    return () => { mounted = false; };
  }, [selectedLine]);

  const canSave = useMemo(() => {
    const hasLine = !!selectedLine || !!customLineName.trim();
    const detourValid = !isDetour || !!detourReason;
    return hasLine && detourValid;
  }, [selectedLine, customLineName, isDetour, detourReason]);

  const handleConfirm = async () => {
    if (!canSave || isSaving) return;
    setIsSaving(true);
    try {
      await onConfirm({
        lineId: selectedLine?.id ?? null,
        customLineName: selectedLine ? null : customLineName.trim() || null,
        isDetour,
        detourReason: isDetour ? detourReason : null,
        detourDescription: isDetour && detourDescription.trim() ? detourDescription.trim() : null,
      });

      // Submit fare report if amount was provided and we have a line + GPS points
      const amount = parseFloat(fareAmount);
      const lineId = selectedLine?.id;
      if (amount > 0 && lineId && recordingId) {
        try {
          const points = getDb()
            .select()
            .from(locationPoints)
            .where(eq(locationPoints.recordingId, recordingId))
            .all();
          if (points.length >= 2) {
            const first = points[0];
            const last = points[points.length - 1];
            await api.submitFareReport({
              lineId,
              deviceId: getDeviceId(),
              amountBob: amount,
              boardingLat: first.latitude,
              boardingLon: first.longitude,
              alightingLat: last.latitude,
              alightingLon: last.longitude,
              source: fareSource === 'chip' ? 'confirmation' : 'registration',
            });
          }
        } catch {
          // Fare submission is best-effort — don't block the recording save
        }
      }
    } finally {
      setIsSaving(false);
    }
  };

  const prepareDetourConfirmation = async () => {
    // Load recorded path from local DB
    let pathPoints: [number, number][] = [];
    if (recordingId) {
      const points = getDb()
        .select()
        .from(locationPoints)
        .where(eq(locationPoints.recordingId, recordingId))
        .all();
      pathPoints = points.map((p) => [p.longitude, p.latitude] as [number, number]);
      setRecordedPath(pathPoints);
    }

    // Identify boarding/alighting municipalities from the recorded
    // GPS endpoints — surfaced to the user above the fare input so
    // they can verify before submitting (CU-08 transparency).
    if (pathPoints.length >= 2) {
      const first = pathPoints[0];
      const last = pathPoints[pathPoints.length - 1];
      try {
        const result = await api.resolveFareZones({
          boardingLon: first[0], boardingLat: first[1],
          alightingLon: last[0], alightingLat: last[1],
        });
        setIdentifiedZones({
          boarding: result.boarding_zone,
          alighting: result.alighting_zone,
        });
      } catch {
        // Best-effort: if the resolver fails, just don't show the
        // identification line — fare submission still works (the
        // server re-resolves at submit time).
        setIdentifiedZones(null);
      }
    }

    // Load line's normal route — first ramal (alphabetical: "main" first
    // when present). Multi-ramal display is handled elsewhere.
    const lineId = selectedLine?.id;
    if (lineId) {
      try {
        const collection = await api.getLineRoute(lineId.toString());
        const first = collection.features?.[0];
        if (first?.geometry?.coordinates) {
          setLineRouteCoords(first.geometry.coordinates as [number, number][]);
        }
      } catch {
        // Endpoint 404s when no active route — leave path empty.
      }
    }

    setShowConfirmation(true);
  };

  const handleSavePress = async () => {
    if (!canSave || isSaving) return;
    if (isDetour) {
      await prepareDetourConfirmation();
    } else {
      await handleConfirm();
    }
  };

  const showDetourPrompt = activeDetour && !detourPromptDismissed;

  // Detour confirmation screen
  if (showConfirmation && isDetour) {
    return (
      <Modal visible={visible} animationType="slide" transparent onRequestClose={() => setShowConfirmation(false)}>
        <View className="flex-1 justify-end bg-black/45">
          <View className="h-4/5 rounded-t-3xl bg-white pt-3">
            <View className="mb-4 h-1 w-10 self-center rounded bg-gray-300" />

            <ScrollView accessible={false} className="flex-1 px-6">
              <View className="mb-3 flex-row items-center">
                <Feather name="alert-triangle" size={22} color="#F97316" />
                <Text className="ml-2 text-[20px] font-bold text-orange-600" testID="modal-detour-confirm-title">Confirmar desvío</Text>
              </View>

              <View className="mb-4 rounded-xl bg-orange-50 p-3">
                <Text className="text-sm text-orange-700">
                  Este desvío se publicará inmediatamente para todos los usuarios de Línea{' '}
                  <Text className="font-bold">{selectedLine?.name ?? customLineName}</Text>.
                </Text>
              </View>

              {/* Map showing normal route (blue) + recorded trip (orange dashed) */}
              <View className="mb-4 overflow-hidden rounded-xl">
                <RouteMap
                  lineRoute={lineRouteCoords.length >= 2 ? { coordinates: lineRouteCoords, name: selectedLine?.name ?? '' } : null}
                  detourPath={recordedPath.length >= 2 ? recordedPath : null}
                  style={{ height: 250 }}
                />
              </View>

              <View className="mb-2 flex-row items-center gap-3">
                <View className="h-1 w-6 rounded bg-[#3D6CB4]" />
                <Text className="text-xs text-gray-500">Ruta normal</Text>
                <View className="h-1 w-6 rounded bg-orange-400" style={{ borderStyle: 'dashed' }} />
                <Text className="text-xs text-gray-500">Tu recorrido (desvío)</Text>
              </View>

              <View className="mb-4 mt-3 rounded-xl bg-gray-50 p-3">
                <Text className="text-sm text-gray-700">
                  <Text className="font-semibold">Razón:</Text> {detourReason ?? 'No especificada'}
                </Text>
                {detourDescription ? (
                  <Text className="mt-1 text-sm text-gray-700">
                    <Text className="font-semibold">Descripción:</Text> {detourDescription}
                  </Text>
                ) : null}
              </View>
            </ScrollView>

            <View className="flex-row gap-3 border-t border-gray-100 px-6 py-4">
              <TouchableOpacity
                className="flex-1 items-center rounded-xl bg-gray-100 py-3.5"
                onPress={() => setShowConfirmation(false)}
              >
                <Text className="text-base font-semibold text-gray-700">Volver</Text>
              </TouchableOpacity>
              <TouchableOpacity
                className="flex-1 items-center rounded-xl bg-orange-500 py-3.5"
                onPress={handleConfirm}
                disabled={isSaving}
              >
                <Text className="text-base font-semibold text-white">{isSaving ? 'Publicando...' : 'Publicar desvío'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    );
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onDiscard}>
      <View className="flex-1 justify-end bg-black/45">
        <View className="h-4/5 rounded-t-3xl bg-white pt-3">
          <View className="mb-4 h-1 w-10 self-center rounded bg-gray-300" />

          <ScrollView accessible={false} className="flex-1 px-6" keyboardShouldPersistTaps="handled">
            {/* Header */}
            <Text className="text-[20px] font-bold text-gray-900" testID="modal-title">Guardar recorrido</Text>
            <Text className="mt-1 mb-4 text-sm text-gray-500">¿En qué línea viajaste?</Text>

            {/* Stats */}
            <View className="mb-5 flex-row items-center justify-center rounded-xl bg-green-50 py-4">
              <View className="items-center px-5">
                <Text className="text-[20px] font-bold text-green-800">{formatDuration(finalDuration)}</Text>
                <Text className="mt-0.5 text-xs text-green-700">Duración</Text>
              </View>
              <View className="h-7 w-px bg-green-200" />
              <View className="items-center px-5">
                <Text className="text-[20px] font-bold text-green-800">{finalPoints}</Text>
                <Text className="mt-0.5 text-xs text-green-700">Puntos</Text>
              </View>
            </View>

            {/* Line dropdown selector */}
            <Text className="mb-2 text-[13px] font-medium text-gray-500">Línea</Text>
            <Pressable
              testID="modal-line-dropdown"
              className="mb-1 flex-row items-center justify-between rounded-xl border-2 border-gray-200 bg-gray-50 px-4 py-3.5"
              onPress={() => setDropdownOpen(!dropdownOpen)}
            >
              <Text className={`text-base ${selectedLine ? 'font-semibold text-gray-900' : 'text-gray-400'}`}>
                {selectedLine ? selectedLine.name : 'Seleccionar línea'}
              </Text>
              <Feather name={dropdownOpen ? 'chevron-up' : 'chevron-down'} size={20} color="#9CA3AF" />
            </Pressable>

            {dropdownOpen && (
              <View className="mb-3 max-h-48 rounded-xl border border-gray-200 bg-white">
                <ScrollView nestedScrollEnabled>
                  {lines.length === 0 ? (
                    <Text className="py-4 text-center text-sm italic text-gray-400">No hay líneas disponibles</Text>
                  ) : (
                    lines.map((item) => {
                      const isSelected = selectedLine?.id === item.id;
                      return (
                        <Pressable
                          key={item.id.toString()}
                          testID={`modal-line-option-${item.id}`}
                          className={`flex-row items-center border-b border-gray-100 px-4 py-3 ${isSelected ? 'bg-sky-50' : ''}`}
                          onPress={() => { setSelectedLine(item); setCustomLineName(''); setDropdownOpen(false); }}
                        >
                          <Text className={`flex-1 text-sm ${isSelected ? 'font-semibold text-[#3D6CB4]' : 'text-gray-700'}`}>
                            {item.name}
                          </Text>
                          {item.status === 'pending' && (
                            <View className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5">
                              <Text className="text-[10px] font-medium text-amber-600">Pendiente</Text>
                            </View>
                          )}
                          {isSelected && <Feather name="check" size={16} color="#3D6CB4" className="ml-2" />}
                        </Pressable>
                      );
                    })
                  )}
                </ScrollView>
              </View>
            )}

            {/* Or create new line */}
            <Text className="mb-2 mt-2 text-[13px] font-medium text-gray-500">O crear nueva línea</Text>
            <TextInput
              className="rounded-xl bg-gray-100 px-4 py-3.5 text-base text-gray-900"
              placeholder="Nombre de la línea"
              placeholderTextColor="#9CA3AF"
              value={customLineName}
              onChangeText={(text) => { setCustomLineName(text); if (text.trim()) setSelectedLine(null); }}
            />

            {/* Matching existing lines — shown while typing a custom name */}
            {customLineName.trim().length >= 1 && !selectedLine && (() => {
              const q = customLineName.trim().toLowerCase();
              const matches = lines.filter((l) => l.name.toLowerCase().includes(q));
              if (matches.length === 0) return null;
              return (
                <View className="mt-1 mb-3 rounded-xl border border-sky-200 bg-sky-50 px-1 py-1">
                  <Text className="px-3 pt-2 pb-1 text-[11px] font-semibold text-sky-600">¿Es alguna de estas?</Text>
                  {matches.slice(0, 5).map((item) => (
                    <Pressable
                      key={item.id.toString()}
                      className="flex-row items-center rounded-lg px-3 py-2.5 active:bg-sky-100"
                      onPress={() => { setSelectedLine(item); setCustomLineName(''); }}
                    >
                      <Feather name="truck" size={14} color="#3D6CB4" />
                      <Text className="ml-2 flex-1 text-sm font-medium text-gray-800">{item.name}</Text>
                      {item.status === 'pending' && (
                        <View className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5">
                          <Text className="text-[10px] font-medium text-amber-600">Pendiente</Text>
                        </View>
                      )}
                    </Pressable>
                  ))}
                </View>
              );
            })()}

            {/* Spacer when no suggestions */}
            {(customLineName.trim().length < 1 || selectedLine) && <View className="mb-4" />}

            {/* Fare input (optional) — chips of previously-reported amounts
                with a free-entry fallback below. CU-09 / RF-26 / RF-28. */}
            {(selectedLine || customLineName.trim()) && (
              <View className="mb-4">
                <Text className="mb-2 text-[13px] font-medium text-gray-500">¿Cuánto salió tu pasaje? (opcional)</Text>
                {/* Identified municipalities (CU-08) — shown so the user
                    can verify the system inferred the right zones before
                    submitting the fare report. */}
                {identifiedZones && (identifiedZones.boarding || identifiedZones.alighting) && (
                  <Text className="mb-2 text-xs text-gray-400">
                    Tarifa para{' '}
                    <Text className="text-gray-600">
                      {identifiedZones.boarding ?? 'zona desconocida'}
                    </Text>
                    {' → '}
                    <Text className="text-gray-600">
                      {identifiedZones.alighting ?? 'zona desconocida'}
                    </Text>
                  </Text>
                )}

                {fareOptions.length > 0 && (
                  <View className="mb-2 flex-row flex-wrap gap-2" testID="modal-fare-chips">
                    {fareOptions.map((opt) => {
                      const selected =
                        fareSource === 'chip' &&
                        parseFloat(fareAmount) === opt.amount_bob;
                      return (
                        <Pressable
                          key={opt.amount_bob}
                          testID={`modal-fare-chip-${opt.amount_bob.toFixed(2)}`}
                          onPress={() => {
                            setFareAmount(opt.amount_bob.toFixed(2));
                            setFareSource('chip');
                          }}
                          className={`flex-row items-center rounded-full border px-3 py-1.5 ${
                            selected
                              ? 'border-[#3D6CB4] bg-[#E7EEF7]'
                              : 'border-gray-200 bg-white'
                          }`}
                        >
                          <Text
                            className={`text-sm font-semibold ${
                              selected ? 'text-[#3D6CB4]' : 'text-gray-700'
                            }`}
                          >
                            Bs {opt.amount_bob.toFixed(2)}
                          </Text>
                          <Text
                            className={`ml-1.5 text-xs ${
                              selected ? 'text-[#3D6CB4] opacity-80' : 'text-gray-400'
                            }`}
                          >
                            ({opt.report_count})
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                )}

                <View className="flex-row items-center rounded-xl bg-gray-100 px-4 py-3.5">
                  <Text className="mr-2 text-base font-semibold text-gray-500">Bs</Text>
                  <TextInput
                    testID="modal-fare-input"
                    className="flex-1 text-base text-gray-900"
                    placeholder={fareOptions.length > 0 ? 'O ingresar otro monto' : '0.00'}
                    placeholderTextColor="#9CA3AF"
                    value={fareAmount}
                    onChangeText={(t) => {
                      setFareAmount(t);
                      setFareSource('free');
                    }}
                    keyboardType="decimal-pad"
                  />
                </View>
              </View>
            )}

            {/* Detour confirmation prompt */}
            {showDetourPrompt && (
              <View className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4">
                <View className="flex-row items-center">
                  <Feather name="alert-triangle" size={18} color="#D97706" />
                  <Text className="ml-2 flex-1 text-sm font-semibold text-amber-800">
                    Línea {activeDetour.line_name} tiene un desvío activo
                  </Text>
                </View>
                <Text className="mt-1 text-[13px] text-amber-700">¿Sigue habiendo desvío?</Text>
                <View className="mt-3 flex-row gap-2">
                  <TouchableOpacity
                    className="flex-1 items-center rounded-lg bg-amber-600 py-2.5"
                    onPress={async () => {
                      if (activeDetour) {
                        try { await api.confirmDetour(activeDetour.id); } catch {}
                      }
                      setDetourPromptDismissed(true);
                    }}
                  >
                    <Text className="text-sm font-semibold text-white">Sí, sigue</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    className="flex-1 items-center rounded-lg bg-gray-200 py-2.5"
                    onPress={() => setDetourPromptDismissed(true)}
                  >
                    <Text className="text-sm font-semibold text-gray-700">No, ya no</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* Detour toggle */}
            {(selectedLine || customLineName.trim()) && (
              <View className="mb-4 rounded-xl border border-gray-200 bg-gray-50 p-4">
                <View className="flex-row items-center justify-between">
                  <View className="flex-row items-center">
                    <Feather name="alert-triangle" size={16} color="#F97316" />
                    <Text className="ml-2 text-base font-medium text-gray-700" testID="modal-detour-label">Es un desvío</Text>
                  </View>
                  <Switch
                    value={isDetour}
                    onValueChange={setIsDetour}
                    trackColor={{ false: '#D1D5DB', true: '#3D6CB4' }}
                    thumbColor="#FFFFFF"
                  />
                </View>

                {isDetour && (
                  <View className="mt-3">
                    <Text className="mb-2 text-[13px] font-medium text-gray-500">Razón del desvío</Text>
                    <View className="flex-row flex-wrap gap-2">
                      {DETOUR_REASONS.map((reason) => {
                        const active = detourReason === reason;
                        return (
                          <Pressable
                            key={reason}
                            className={`rounded-full border px-4 py-2 ${active ? 'border-[#3D6CB4] bg-sky-100' : 'border-gray-300 bg-white'}`}
                            onPress={() => setDetourReason(reason)}
                          >
                            <Text className={`text-sm font-medium ${active ? 'text-[#3D6CB4]' : 'text-gray-600'}`}>
                              {reason}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </View>
                    <TextInput
                      className="mt-3 rounded-xl bg-white px-4 py-3 text-base text-gray-900"
                      placeholder="Descripción (opcional)"
                      placeholderTextColor="#9CA3AF"
                      value={detourDescription}
                      onChangeText={setDetourDescription}
                      multiline
                    />
                  </View>
                )}
              </View>
            )}
          </ScrollView>

          {/* Action buttons */}
          <View className="flex-row gap-3 border-t border-gray-100 px-6 py-4">
            <TouchableOpacity className="flex-1 items-center rounded-xl bg-gray-100 py-3.5" onPress={onDiscard}>
              <Text className="text-base font-semibold text-gray-700" testID="modal-discard-btn">Descartar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="modal-save-btn"
              className={`flex-1 items-center rounded-xl py-3.5 ${!canSave ? 'bg-[#3D6CB4]/40' : isDetour ? 'bg-orange-500' : 'bg-[#3D6CB4]'}`}
              onPress={handleSavePress}
              disabled={!canSave || isSaving}
            >
              <Text className="text-base font-semibold text-white">{isSaving ? 'Guardando...' : isDetour ? 'Revisar desvío' : 'Guardar'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}
