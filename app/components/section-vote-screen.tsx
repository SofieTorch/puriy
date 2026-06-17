/**
 * Section-by-section voting screen.
 * Steps through contiguous edge groups, showing each on a map
 * with the full route as gray context.
 *
 * After the last section is voted on, if the line has ≥2 active
 * ramales the screen shows a descriptor step scoped to the route
 * the user just voted on — that's a high-intent moment to capture
 * distinguishing features (orange flags, Univalle sticker, …).
 * Single-ramal lines skip straight to the summary.
 */
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import RamalDescriptorsScreen from '@/components/ramal-descriptors-screen';
import RouteMap, { LineRoute } from '@/components/route-map';
import api from '@/services/api';
import { getDeviceId } from '@/services/device-id';

interface VoteableSection {
  section_index: number;
  trip_count: number;
  geometry: number[][];
  edges: { id: string }[];
}

interface SectionVoteScreenProps {
  visible: boolean;
  lineId: string;
  /** The Route the user is voting on. Used to scope the descriptor
   * step to the specific ramal they just confirmed. */
  routeId: string;
  lineName: string;
  routeGeojson: { geometry?: { coordinates?: number[][] } } | null;
  sections: VoteableSection[];
  onDone: () => void;
}

type Step = 'voting' | 'describing' | 'done';

export default function SectionVoteScreen({
  visible,
  lineId,
  routeId,
  lineName,
  routeGeojson,
  sections,
  onDone,
}: SectionVoteScreenProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [votes, setVotes] = useState<Record<number, 'approve' | 'reject'>>({});
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<Step>('voting');
  // Endpoint zones + street summary for the ramal the user just voted
  // on — passed to the descriptor screen header. `null` until we've
  // confirmed the line has ≥2 ramales (otherwise we skip).
  const [ramalIdentity, setRamalIdentity] = useState<{
    endpointZones: (string | null)[];
    streetSummary: string[];
  } | null>(null);

  const section = sections[currentIndex];
  const isLast = currentIndex === sections.length - 1;

  // Full route as gray context
  const fullRoute: LineRoute | null = routeGeojson?.geometry?.coordinates
    ? { coordinates: routeGeojson.geometry.coordinates as [number, number][], name: lineName }
    : null;

  // Current section as highlight
  const sectionCoords: [number, number][] | null = section?.geometry?.length >= 2
    ? (section.geometry as [number, number][])
    : null;

  const handleVote = async (vote: 'approve' | 'reject') => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await api.submitVote(lineId, getDeviceId(), vote, section.section_index);
      setVotes((prev) => ({ ...prev, [section.section_index]: vote }));

      if (isLast) {
        // Decide whether to show the descriptor step before the summary.
        await maybeStartDescribing();
      } else {
        setCurrentIndex((i) => i + 1);
      }
    } catch (err) {
      console.error('Vote failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const maybeStartDescribing = async () => {
    try {
      const collection = await api.getLineRoute(lineId);
      const features = collection.features ?? [];
      // Only ask for descriptors when there's actual disambiguation
      // to do — single-ramal lines skip straight to the summary.
      if (features.length < 2) {
        setStep('done');
        return;
      }
      const match = features.find((f) => f.properties?.route_id === routeId);
      if (!match) {
        setStep('done');
        return;
      }
      setRamalIdentity({
        endpointZones: match.properties.endpoint_zones ?? [null, null],
        streetSummary: match.properties.street_summary ?? [],
      });
      setStep('describing');
    } catch {
      // Best-effort: don't block the user if the lookup fails.
      setStep('done');
    }
  };

  const handleClose = () => {
    // Reset state for next time
    setCurrentIndex(0);
    setVotes({});
    setStep('voting');
    setRamalIdentity(null);
    onDone();
  };

  // Auto-stay on 'voting' if the screen was reopened (defensive).
  useEffect(() => {
    if (!visible) {
      setStep('voting');
      setCurrentIndex(0);
      setVotes({});
      setRamalIdentity(null);
    }
  }, [visible]);

  // Descriptor step — only reached when the line has ≥2 ramales.
  if (step === 'describing' && ramalIdentity) {
    return (
      <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
        <View className="flex-1 bg-white">
          <View className="flex-row items-center border-b border-gray-100 px-4 pb-3 pt-14">
            <View className="flex-1">
              <Text className="text-lg font-bold text-gray-900">
                Describí esta micro
              </Text>
              <Text className="text-sm text-gray-400">Línea {lineName}</Text>
            </View>
            <Pressable
              className="rounded-md px-3 py-1.5"
              onPress={() => setStep('done')}
            >
              <Text className="text-sm font-medium text-gray-500">Saltar</Text>
            </Pressable>
          </View>
          <RamalDescriptorsScreen
            routeId={routeId}
            deviceId={getDeviceId()}
            endpointZones={ramalIdentity.endpointZones}
            streetSummary={ramalIdentity.streetSummary}
          />
          <View className="border-t border-gray-100 px-6 pb-10 pt-4">
            <Pressable
              className="w-full items-center rounded-xl bg-[#3D6CB4] py-4"
              onPress={() => setStep('done')}
            >
              <Text className="text-base font-semibold text-white">Listo</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    );
  }

  // Summary screen
  if (step === 'done') {
    const approved = Object.values(votes).filter((v) => v === 'approve').length;
    const rejected = Object.values(votes).filter((v) => v === 'reject').length;

    return (
      <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
        <View className="flex-1 items-center justify-center bg-white px-8">
          <View className="mb-6 h-20 w-20 items-center justify-center rounded-full bg-green-100">
            <Feather name="check" size={40} color="#22C55E" />
          </View>
          <Text className="mb-2 text-2xl font-bold text-gray-900">Votación completa</Text>
          <Text className="mb-1 text-base text-gray-500">
            Votaste en {sections.length} {sections.length === 1 ? 'sección' : 'secciones'}
          </Text>
          <Text className="mb-8 text-sm text-gray-400">
            {approved > 0 && `${approved} aprobada${approved > 1 ? 's' : ''}`}
            {approved > 0 && rejected > 0 && ', '}
            {rejected > 0 && `${rejected} rechazada${rejected > 1 ? 's' : ''}`}
          </Text>
          <Pressable
            className="w-full items-center rounded-xl bg-[#3D6CB4] py-4"
            onPress={handleClose}
          >
            <Text className="text-base font-semibold text-white">Volver a Contribuir</Text>
          </Pressable>
        </View>
      </Modal>
    );
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
      <View className="flex-1 bg-white">
        {/* Header */}
        <View className="flex-row items-center border-b border-gray-100 px-4 pb-3 pt-14">
          <Pressable className="mr-3 p-1" onPress={handleClose}>
            <Feather name="arrow-left" size={24} color="#333" />
          </Pressable>
          <View className="flex-1">
            <Text className="text-lg font-bold text-gray-900">
              Sección {currentIndex + 1} de {sections.length}
            </Text>
            <Text className="text-sm text-gray-400">Línea {lineName}</Text>
          </View>
        </View>

        {/* Map */}
        <RouteMap
          lineRoute={fullRoute}
          highlightPath={sectionCoords}
          style={{ flex: 1 }}
        />

        {/* Trip count badge */}
        <View className="items-center border-t border-gray-100 px-6 pt-4">
          <View className="flex-row items-center rounded-full bg-sky-50 px-5 py-2.5">
            <MaterialCommunityIcons name="road-variant" size={18} color="#3D6CB4" />
            <Text className="ml-2 text-sm font-semibold text-[#3D6CB4]">
              Viajaste esta sección {section?.trip_count ?? 0} {section?.trip_count === 1 ? 'vez' : 'veces'}
            </Text>
          </View>
        </View>

        {/* Vote buttons */}
        <View className="flex-row gap-3 px-6 pb-10 pt-4">
          <Pressable
            className="flex-1 flex-row items-center justify-center rounded-xl bg-brand-red py-4 active:opacity-90"
            onPress={() => handleVote('reject')}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Feather name="x" size={20} color="#fff" />
                <Text className="ml-2 text-base font-semibold text-white">Rechazar</Text>
              </>
            )}
          </Pressable>
          <Pressable
            className="flex-1 flex-row items-center justify-center rounded-xl bg-brand-green py-4 active:opacity-90"
            onPress={() => handleVote('approve')}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Feather name="check" size={20} color="#fff" />
                <Text className="ml-2 text-base font-semibold text-white">Aprobar</Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
