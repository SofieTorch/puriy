import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import { api, NearbyLine, PendingLine, VoteableSegment } from '@/services/api';
import { getDeviceId } from '@/services/device-id';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from 'react-native';

export default function ContributeScreen() {
  const [pending, setPending] = useState<PendingLine[]>([]);
  const [nearbyLines, setNearbyLines] = useState<NearbyLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [votingLineId, setVotingLineId] = useState<string | null>(null);
  const [segment, setSegment] = useState<VoteableSegment | null>(null);

  const deviceId = getDeviceId();
  const tabBarHeight = useBottomTabBarHeight();

  const fetchPending = useCallback(async () => {
    try {
      const [lines, nearby] = await Promise.all([
        api.getPendingVotes(deviceId).catch(() => []),
        api.getNearbyLines(deviceId).catch(() => []),
      ]);
      setPending(lines);
      setNearbyLines(nearby);
    } catch {
      setPending([]);
      setNearbyLines([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [deviceId]);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  const onRefresh = () => {
    setRefreshing(true);
    setSegment(null);
    setVotingLineId(null);
    fetchPending();
  };

  const loadSegment = async (lineId: string) => {
    setVotingLineId(lineId);
    try {
      const seg = await api.getVoteableSegment(lineId, deviceId);
      setSegment(seg);
    } catch {
      setSegment(null);
      Alert.alert('Error', 'No se pudo cargar el segmento de ruta.');
    }
  };

  const submitLineVote = async (lineId: string, vote: 'approve' | 'reject') => {
    try {
      await api.submitLineVote(lineId, deviceId, vote);
      setNearbyLines((prev) => prev.filter((l) => l.line_id !== lineId));
    } catch {
      Alert.alert('Error', 'No se pudo enviar tu voto.');
    }
  };

  const submitVote = async (lineId: string, vote: 'approve' | 'reject') => {
    try {
      const result = await api.submitVote(lineId, deviceId, vote);
      Alert.alert(
        vote === 'approve' ? 'Aprobado' : 'Rechazado',
        `Votaste en ${result.edges_voted} segmentos.`
      );
      // Refresh to remove voted line
      setSegment(null);
      setVotingLineId(null);
      fetchPending();
    } catch {
      Alert.alert('Error', 'No se pudo enviar tu voto.');
    }
  };

  return (
    <View accessible={false} className="flex-1">
      <ScrollView
        accessible={false}
        className="flex-1 px-4"
        contentContainerStyle={{ paddingBottom: tabBarHeight + 12 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {loading ? (
          <View className="items-center py-20">
            <ActivityIndicator size="large" color="#09A6F3" />
          </View>
        ) : pending.length === 0 && nearbyLines.length === 0 ? (
          <View className="items-center gap-3 py-20">
            <MaterialCommunityIcons
              name="check-circle-outline"
              size={48}
              color="#9CA3AF"
            />
            <Text testID="contribute-empty" className="text-center text-base text-gray-400">
              No hay rutas pendientes para votar.
            </Text>
            <Text className="text-center text-sm text-gray-400">
              Registra recorridos para contribuir.
            </Text>
          </View>
        ) : (
          <View className="gap-4 py-4">
            {/* Line familiarity voting */}
            {nearbyLines.length > 0 && (
              <>
                <Text testID="contribute-lines-title" className="text-lg font-semibold text-gray-800">
                  ¿Conoces estas líneas?
                </Text>
                {nearbyLines.map((line, idx) => (
                  <View
                    key={line.line_id}
                    className="flex-row items-center justify-between rounded-2xl border border-gray-200 bg-white px-4 py-3"
                  >
                    <View className="flex-1 gap-0.5">
                      <Text className="text-base font-medium text-gray-800">
                        Línea {line.line_name}
                      </Text>
                      {line.line_description && (
                        <Text
                          className="text-sm text-gray-500"
                          numberOfLines={1}
                        >
                          {line.line_description}
                        </Text>
                      )}
                    </View>
                    <View className="flex-row gap-2">
                      <Pressable
                        testID={`contribute-line-approve-${idx}`}
                        className="h-9 w-9 items-center justify-center rounded-full bg-green-50"
                        onPress={() => submitLineVote(line.line_id, 'approve')}
                      >
                        <MaterialCommunityIcons
                          name="check"
                          size={20}
                          color="#22C55E"
                        />
                      </Pressable>
                      <Pressable
                        testID={`contribute-line-reject-${idx}`}
                        className="h-9 w-9 items-center justify-center rounded-full bg-red-50"
                        onPress={() => submitLineVote(line.line_id, 'reject')}
                      >
                        <MaterialCommunityIcons
                          name="close"
                          size={20}
                          color="#EF4444"
                        />
                      </Pressable>
                    </View>
                  </View>
                ))}
              </>
            )}

            {/* Route edge voting */}
            {pending.length > 0 && (
              <Text testID="contribute-routes-title" className="text-lg font-semibold text-gray-800">
                ¿Estas rutas son correctas?
              </Text>
            )}

            {pending.map((line, idx) => (
              <View
                key={line.line_id}
                className="overflow-hidden rounded-2xl border border-gray-200 bg-white"
              >
                {/* Line info */}
                <View className="gap-1 p-4">
                  <Text className="text-base font-semibold text-gray-800">
                    Línea {line.line_name}
                  </Text>
                  {line.line_description && (
                    <Text
                      className="text-sm text-gray-500"
                      numberOfLines={2}
                    >
                      {line.line_description}
                    </Text>
                  )}
                  <Text className="mt-1 text-xs text-gray-400">
                    {line.pending_edge_count} segmentos pendientes de{' '}
                    {line.total_edge_count} totales
                  </Text>
                </View>

                {/* Segment detail (if expanded) */}
                {votingLineId === line.line_id && segment && (
                  <View className="border-t border-gray-100 bg-gray-50 px-4 py-3">
                    <Text className="text-sm text-gray-600">
                      {segment.edges.length} segmentos para revisar
                    </Text>
                  </View>
                )}

                {/* Actions */}
                <View className="flex-row border-t border-gray-100">
                  {votingLineId !== line.line_id ? (
                    <Pressable
                      className="flex-1 items-center py-3"
                      onPress={() => loadSegment(line.line_id)}
                    >
                      <Text className="text-sm font-medium text-[#09A6F3]">
                        Ver ruta
                      </Text>
                    </Pressable>
                  ) : (
                    <>
                      <Pressable
                        testID={`contribute-route-approve-${idx}`}
                        className="flex-1 flex-row items-center justify-center gap-1.5 border-r border-gray-100 py-3"
                        onPress={() =>
                          submitVote(line.line_id, 'approve')
                        }
                      >
                        <MaterialCommunityIcons
                          name="check-circle"
                          size={20}
                          color="#22C55E"
                        />
                        <Text className="text-sm font-medium text-green-600">
                          Aprobar
                        </Text>
                      </Pressable>
                      <Pressable
                        testID={`contribute-route-reject-${idx}`}
                        className="flex-1 flex-row items-center justify-center gap-1.5 py-3"
                        onPress={() =>
                          submitVote(line.line_id, 'reject')
                        }
                      >
                        <MaterialCommunityIcons
                          name="close-circle"
                          size={20}
                          color="#EF4444"
                        />
                        <Text className="text-sm font-medium text-red-500">
                          Rechazar
                        </Text>
                      </Pressable>
                    </>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}
