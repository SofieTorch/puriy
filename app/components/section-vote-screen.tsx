/**
 * Section-by-section voting screen.
 * Steps through contiguous edge groups, showing each on a map
 * with the full route as gray context.
 */
import React, { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { MaterialCommunityIcons } from '@expo/vector-icons';

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
  lineName: string;
  routeGeojson: { geometry?: { coordinates?: number[][] } } | null;
  sections: VoteableSection[];
  onDone: () => void;
}

export default function SectionVoteScreen({
  visible,
  lineId,
  lineName,
  routeGeojson,
  sections,
  onDone,
}: SectionVoteScreenProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [votes, setVotes] = useState<Record<number, 'approve' | 'reject'>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

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
        setDone(true);
      } else {
        setCurrentIndex((i) => i + 1);
      }
    } catch (err) {
      console.error('Vote failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    // Reset state for next time
    setCurrentIndex(0);
    setVotes({});
    setDone(false);
    onDone();
  };

  // Summary screen
  if (done) {
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
            className="w-full items-center rounded-xl bg-[#09A6F3] py-4"
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
            <MaterialCommunityIcons name="road-variant" size={18} color="#09A6F3" />
            <Text className="ml-2 text-sm font-semibold text-[#09A6F3]">
              Viajaste esta sección {section?.trip_count ?? 0} {section?.trip_count === 1 ? 'vez' : 'veces'}
            </Text>
          </View>
        </View>

        {/* Vote buttons */}
        <View className="flex-row gap-4 px-6 pb-10 pt-4">
          <Pressable
            className="flex-1 flex-row items-center justify-center rounded-xl border-2 border-red-200 bg-red-50 py-4"
            onPress={() => handleVote('reject')}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#EF4444" />
            ) : (
              <>
                <Feather name="x" size={20} color="#EF4444" />
                <Text className="ml-2 text-base font-semibold text-red-500">Rechazar</Text>
              </>
            )}
          </Pressable>
          <Pressable
            className="flex-1 flex-row items-center justify-center rounded-xl border-2 border-green-200 bg-green-50 py-4"
            onPress={() => handleVote('approve')}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#22C55E" />
            ) : (
              <>
                <Feather name="check" size={20} color="#22C55E" />
                <Text className="ml-2 text-base font-semibold text-green-600">Aprobar</Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
