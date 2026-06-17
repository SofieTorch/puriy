/**
 * Vote-on-existing-first descriptors UI for one ramal (Route).
 *
 * Flow:
 * 1. Show existing descriptors as a list, top-to-bottom by votes.
 *    Each row has an upvote chip (filled when the user already voted).
 * 2. Below the list: a "Ninguna describe esta línea" button. Only
 *    after tapping it does a TextInput appear for typing a new one.
 * 3. On submit: hit POST. If the server returns 409 with `existing`,
 *    pulse-highlight the matching existing row instead of creating a
 *    duplicate.
 *
 * Decision #5: this screen never renders `ramal_label` — the ramal
 * is identified by its endpoint zones and street summary in the
 * header, both passed in by the parent.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';

import api, { ApiError, RamalDescriptor } from '@/services/api';

interface Props {
  routeId: string;
  deviceId: string;
  endpointZones: (string | null)[];
  streetSummary: string[];
}

export default function RamalDescriptorsScreen({
  routeId, deviceId, endpointZones, streetSummary,
}: Props) {
  const [descriptors, setDescriptors] = useState<RamalDescriptor[]>([]);
  const [loading, setLoading] = useState(true);
  const [composing, setComposing] = useState(false);
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.getRamalDescriptors(routeId, deviceId);
      setDescriptors(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar descripciones');
    } finally {
      setLoading(false);
    }
  }, [routeId, deviceId]);

  useEffect(() => { refresh(); }, [refresh]);

  // Auto-clear pulse-highlight after ~2s.
  useEffect(() => {
    if (!highlightedId) return;
    const t = setTimeout(() => setHighlightedId(null), 2000);
    return () => clearTimeout(t);
  }, [highlightedId]);

  const toggleVote = async (d: RamalDescriptor) => {
    // Optimistic update.
    const next = d.voted_by_me
      ? { ...d, voted_by_me: false, votes_count: Math.max(0, d.votes_count - 1) }
      : { ...d, voted_by_me: true, votes_count: d.votes_count + 1 };
    setDescriptors(prev => prev.map(x => (x.id === d.id ? next : x)));
    try {
      const updated = d.voted_by_me
        ? await api.unvoteRamalDescriptor(routeId, d.id, deviceId)
        : await api.upvoteRamalDescriptor(routeId, d.id, deviceId);
      setDescriptors(prev => prev.map(x => (x.id === d.id ? updated : x)));
    } catch {
      // Roll back on failure.
      setDescriptors(prev => prev.map(x => (x.id === d.id ? d : x)));
    }
  };

  const submitNew = async () => {
    const text = draft.trim();
    if (!text) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createRamalDescriptor(routeId, text, deviceId);
      setDescriptors(prev => [created, ...prev]);
      setDraft('');
      setComposing(false);
      setHighlightedId(created.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body?.detail?.existing) {
        const existing = e.body.detail.existing as RamalDescriptor;
        // Server already has this descriptor. Surface it (refresh in
        // case votes changed since we loaded) and pulse-highlight.
        await refresh();
        setHighlightedId(existing.id);
        setDraft('');
        setComposing(false);
      } else {
        setError(e instanceof Error ? e.message : 'Error al enviar');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const start = endpointZones[0];
  const end = endpointZones[1];
  const endpointLabel = start && end ? `${start} → ${end}` : start || end || null;
  const streetsLabel = streetSummary.slice(0, 4).join(' · ');

  return (
    <View className="flex-1 bg-white px-4 py-3">
      {/* Header — identifies the ramal without ever showing ramal_label. */}
      <View className="mb-3 border-b border-gray-100 pb-3">
        {endpointLabel && (
          <Text className="text-base font-semibold text-brand-ink">{endpointLabel}</Text>
        )}
        {streetsLabel && (
          <Text className="text-xs text-gray-500" numberOfLines={2}>{streetsLabel}</Text>
        )}
        <Text className="mt-2 text-sm text-gray-700">
          ¿Qué seña tiene esta micro/trufi? Toca el ✓ si reconoces alguna,
          o agrega una nueva si ninguna calza.
        </Text>
      </View>

      {loading ? (
        <ActivityIndicator className="mt-6" />
      ) : descriptors.length === 0 ? (
        <Text className="text-sm italic text-gray-500">
          Aún no hay descripciones. Sé el primero en agregar una.
        </Text>
      ) : (
        <View>
          {descriptors.map(d => (
            <Pressable
              key={d.id}
              onPress={() => toggleVote(d)}
              className={
                'mb-2 flex-row items-center justify-between rounded-lg border px-3 py-2 ' +
                (highlightedId === d.id ? 'border-[#3D6CB4] bg-[#E7EEF7]' : 'border-brand-line bg-white')
              }
            >
              <Text className="flex-1 pr-3 text-sm text-brand-ink">{d.text}</Text>
              <View className="flex-row items-center">
                <Text className="mr-2 text-xs font-semibold text-gray-600">{d.votes_count}</Text>
                <View
                  className={
                    'h-7 w-7 items-center justify-center rounded-full ' +
                    (d.voted_by_me ? 'bg-[#3D6CB4]' : 'bg-gray-100')
                  }
                >
                  <Feather
                    name="check"
                    size={14}
                    color={d.voted_by_me ? 'white' : '#9CA3AF'}
                  />
                </View>
              </View>
            </Pressable>
          ))}
        </View>
      )}

      {/* Compose area — gated behind an explicit button to encourage
          voting on existing options before creating a new one. */}
      <View className="mt-4">
        {!composing ? (
          <Pressable
            onPress={() => setComposing(true)}
            className="flex-row items-center justify-center rounded-lg border border-dashed border-gray-300 px-3 py-2"
          >
            <Feather name="plus" size={14} color="#6B7280" />
            <Text className="ml-1.5 text-sm text-gray-600">
              Ninguna describe esta línea
            </Text>
          </Pressable>
        ) : (
          <View>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Ej: lleva banderines naranjas en frente"
              placeholderTextColor="#9CA3AF"
              maxLength={200}
              multiline
              editable={!submitting}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-brand-ink"
            />
            <View className="mt-2 flex-row justify-end">
              <Pressable
                onPress={() => { setComposing(false); setDraft(''); setError(null); }}
                disabled={submitting}
                className="mr-2 rounded-md px-3 py-1.5"
              >
                <Text className="text-sm text-gray-600">Cancelar</Text>
              </Pressable>
              <Pressable
                onPress={submitNew}
                disabled={submitting || !draft.trim()}
                className={
                  'rounded-md px-3 py-1.5 ' +
                  (submitting || !draft.trim() ? 'bg-gray-200' : 'bg-[#3D6CB4]')
                }
              >
                <Text className={'text-sm font-semibold ' + (submitting || !draft.trim() ? 'text-gray-500' : 'text-white')}>
                  {submitting ? 'Enviando...' : 'Enviar'}
                </Text>
              </Pressable>
            </View>
          </View>
        )}
        {error && <Text className="mt-2 text-xs text-red-500">{error}</Text>}
      </View>
    </View>
  );
}
