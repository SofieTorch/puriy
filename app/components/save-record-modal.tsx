import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, Modal, Text, TextInput, TouchableOpacity, View } from 'react-native';

import type { Line } from '@/services/api';
import { getLines } from '@/services/line-cache';
import { styles } from '../styles/save-record-modal';

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
      <View style={styles.modalOverlay}>
        <View style={styles.modalSheet}>
          <View style={styles.modalHandle} />

          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Select line</Text>
            <Text style={styles.modalSubtitle}>Which line did you ride?</Text>
          </View>

          <View style={styles.modalSummary}>
            <View style={styles.modalSummaryItem}>
              <Text style={styles.modalSummaryValue}>{formatDuration(finalDuration)}</Text>
              <Text style={styles.modalSummaryLabel}>Duration</Text>
            </View>
            <View style={styles.modalSummaryDivider} />
            <View style={styles.modalSummaryItem}>
              <Text style={styles.modalSummaryValue}>{finalPoints}</Text>
              <Text style={styles.modalSummaryLabel}>Points</Text>
            </View>
          </View>

          <FlatList
            data={lines}
            keyExtractor={(item) => item.id.toString()}
            renderItem={({ item }) => {
              const isSelected = selectedLine?.id === item.id;
              return (
                <TouchableOpacity
                  style={[styles.lineCard, isSelected && styles.lineCardSelected]}
                  onPress={() => {
                    setSelectedLine(item);
                    setCustomLineName('');
                  }}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.lineName, isSelected && styles.lineNameSelected]}>{item.name}</Text>
                  {item.description && (
                    <Text style={styles.lineDescription} numberOfLines={2}>
                      {item.description}
                    </Text>
                  )}
                </TouchableOpacity>
              );
            }}
            style={styles.lineList}
            contentContainerStyle={styles.lineListContent}
            ListEmptyComponent={<Text style={styles.noLines}>No lines available.</Text>}
            ListFooterComponent={
              <View style={styles.newLineSection}>
                <Text style={styles.newLineLabel}>Or add new line</Text>
                <TextInput
                  style={styles.newLineInput}
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

          <View style={styles.modalActions}>
            <TouchableOpacity style={styles.modalBtnCancel} onPress={onDiscard}>
              <Text style={styles.modalBtnCancelText}>Discard</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modalBtnConfirm, !canSave && styles.modalBtnConfirmDisabled]}
              onPress={handleConfirm}
              disabled={!canSave || isSaving}
            >
              <Text style={styles.modalBtnConfirmText}>{isSaving ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}
