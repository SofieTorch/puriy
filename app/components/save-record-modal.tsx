import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, Modal, Text, TextInput, TouchableOpacity, View } from 'react-native';

import type { Line } from '@/services/api';
import { getLines } from '@/services/line-cache';

type SaveRecordModalProps = {
  visible: boolean;
  finalDuration: number;
  finalPoints: number;
  formatDuration: (seconds: number) => string;
  onDiscard: () => void;
  onConfirm: (selection: { lineId: number | null; customLineName: string | null }) => Promise<void>;
};

export default function SaveRecordModal({
  visible,
  finalDuration,
  finalPoints,
  formatDuration,
  onDiscard,
  onConfirm,
}: SaveRecordModalProps) {
  const [lines, setLines] = useState<Line[]>([]);
  const [selectedLine, setSelectedLine] = useState<Line | null>(null);
  const [customLineName, setCustomLineName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!visible) return;

    let mounted = true;
    const fetchLines = async () => {
      try {
        const data = await getLines();
        if (mounted) setLines(data);
      } catch (error) {
        console.error('Failed to fetch lines:', error);
        if (mounted) setLines([]);
      }
    };

    setSelectedLine(null);
    setCustomLineName('');
    setIsSaving(false);
    fetchLines();

    return () => {
      mounted = false;
    };
  }, [visible]);

  const canSave = useMemo(() => !!selectedLine || !!customLineName.trim(), [selectedLine, customLineName]);

  const handleConfirm = async () => {
    if (!canSave || isSaving) return;
    setIsSaving(true);
    try {
      await onConfirm({
        lineId: selectedLine?.id ?? null,
        customLineName: selectedLine ? null : customLineName.trim() || null,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onDiscard}>
      <View className="flex-1 justify-end bg-black/45">
        <View className="h-4/5 rounded-t-3xl bg-white pt-3">
          <View className="mb-4 h-1 w-10 self-center rounded bg-gray-300" />

          <View className="mb-2 px-6">
            <Text className="text-[20px] font-bold text-gray-900">Select line</Text>
            <Text className="mt-1 text-sm text-gray-500">Which line did you ride?</Text>
          </View>

          <View className="mx-6 mb-4 flex-row items-center justify-center rounded-xl bg-green-50 py-4">
            <View className="items-center px-5">
              <Text className="text-[20px] font-bold text-green-800">{formatDuration(finalDuration)}</Text>
              <Text className="mt-0.5 text-xs text-green-700">Duration</Text>
            </View>
            <View className="h-7 w-px bg-green-200" />
            <View className="items-center px-5">
              <Text className="text-[20px] font-bold text-green-800">{finalPoints}</Text>
              <Text className="mt-0.5 text-xs text-green-700">Points</Text>
            </View>
          </View>

          <FlatList
            data={lines}
            keyExtractor={(item) => item.id.toString()}
            renderItem={({ item }) => {
              const isSelected = selectedLine?.id === item.id;
              return (
                <TouchableOpacity
                  className={`mb-2.5 rounded-xl border-2 p-4 ${
                    isSelected ? 'border-[#09A6F3] bg-sky-100' : 'border-transparent bg-gray-100'
                  }`}
                  onPress={() => {
                    setSelectedLine(item);
                    setCustomLineName('');
                  }}
                  activeOpacity={0.7}
                >
                  <Text className={`text-base font-semibold ${isSelected ? 'text-[#09A6F3]' : 'text-gray-700'}`}>
                    {item.name}
                  </Text>
                  {item.description && (
                    <Text className="mt-1 text-[13px] text-gray-500" numberOfLines={2}>
                      {item.description}
                    </Text>
                  )}
                </TouchableOpacity>
              );
            }}
            className="px-6"
            contentContainerClassName="pb-6"
            ListEmptyComponent={<Text className="mt-6 text-center italic text-gray-500/60">No lines available.</Text>}
            ListFooterComponent={
              <View className="mt-4 border-t border-gray-200 pt-4">
                <Text className="mb-2 text-[13px] font-medium text-gray-500">Or add new line</Text>
                <TextInput
                  className="rounded-xl bg-gray-100 px-4 py-3.5 text-base text-gray-900"
                  placeholder="Enter line name"
                  placeholderTextColor="#9CA3AF"
                  value={customLineName}
                  onChangeText={(text) => {
                    setCustomLineName(text);
                    if (text.trim()) setSelectedLine(null);
                  }}
                />
              </View>
            }
          />

          <View className="flex-row gap-3 border-t border-gray-100 px-6 py-4">
            <TouchableOpacity className="flex-1 items-center rounded-xl bg-gray-100 py-3.5" onPress={onDiscard}>
              <Text className="text-base font-semibold text-gray-700">Discard</Text>
            </TouchableOpacity>
            <TouchableOpacity
              className={`flex-1 items-center rounded-xl py-3.5 ${!canSave ? 'bg-[#09A6F3]/40' : 'bg-[#09A6F3]'}`}
              onPress={handleConfirm}
              disabled={!canSave || isSaving}
            >
              <Text className="text-base font-semibold text-white">{isSaving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}
