import Feather from '@expo/vector-icons/Feather';
import { useCallback, useState } from 'react';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';

import Header from '@/components/header';
import { SavedTrip } from '@/db/schema';
import { DirectionsResponse } from '@/services/api';
import { deleteTrip, getTodayTrips, parseRouteJson } from '@/services/saved-trips';

const BLUE = '#09A6F3';

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const mins = Math.round(seconds / 60);
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}min` : `${mins} min`;
}

function busLines(route: DirectionsResponse): string[] {
  const names: string[] = [];
  for (const leg of route.legs) {
    if (leg.mode === 'bus' && leg.line_name && !names.includes(leg.line_name)) {
      names.push(leg.line_name);
    }
  }
  return names;
}

export default function FavoritesScreen() {
  const [trips, setTrips] = useState<SavedTrip[]>([]);

  useFocusEffect(
    useCallback(() => {
      setTrips(getTodayTrips());
    }, [])
  );

  const handleDelete = (trip: SavedTrip) => {
    Alert.alert('Eliminar ruta', `¿Eliminar "${trip.originName} → ${trip.destName}"?`, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Eliminar',
        style: 'destructive',
        onPress: () => {
          deleteTrip(trip.id);
          setTrips(getTodayTrips());
        },
      },
    ]);
  };

  const commutes = trips.filter((t) => t.type === 'commute');
  const oneTime = trips.filter((t) => t.type === 'one_time');

  return (
    <SafeAreaView className="flex-1 bg-[#09A6F3]">
      <View className="flex-1 bg-white">
        <Header title="Favoritos" />

        <ScrollView className="flex-1 px-5 pt-6">
          {trips.length === 0 ? (
            <View className="items-center gap-3 py-20">
              <Feather name="bookmark" size={48} color="#D1D5DB" />
              <Text className="text-center text-base text-gray-400">
                No tienes rutas guardadas.
              </Text>
              <Text className="text-center text-sm text-gray-400">
                Busca una ruta y toca "Guardar" para verla aquí.
              </Text>
            </View>
          ) : (
            <>
              {commutes.length > 0 && (
                <>
                  <Text className="mb-3 text-lg font-semibold text-gray-800">
                    Recurrentes
                  </Text>
                  {commutes.map((trip) => (
                    <TripCard key={trip.id} trip={trip} onDelete={handleDelete} />
                  ))}
                </>
              )}

              {oneTime.length > 0 && (
                <>
                  <Text className="mb-3 mt-4 text-lg font-semibold text-gray-800">
                    Para hoy
                  </Text>
                  {oneTime.map((trip) => (
                    <TripCard key={trip.id} trip={trip} onDelete={handleDelete} />
                  ))}
                </>
              )}
            </>
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function TripCard({
  trip,
  onDelete,
}: {
  trip: SavedTrip;
  onDelete: (trip: SavedTrip) => void;
}) {
  const route = parseRouteJson(trip);
  const lines = busLines(route);

  return (
    <View className="mb-3 rounded-2xl border border-gray-200 bg-white p-4">
      <View className="mb-2 flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-base font-semibold text-gray-800" numberOfLines={1}>
            {trip.originName}
          </Text>
          <Text className="text-sm text-gray-500" numberOfLines={1}>
            → {trip.destName}
          </Text>
        </View>
        <Pressable className="ml-2 p-1" onPress={() => onDelete(trip)}>
          <Feather name="trash-2" size={16} color="#9CA3AF" />
        </Pressable>
      </View>

      {/* Time + distance */}
      <View className="mb-2 flex-row items-center gap-3">
        <Text className="text-lg font-bold text-gray-800">
          {formatDuration(route.total_duration_s)}
        </Text>
        <Text className="text-sm text-gray-400">
          {formatDistance(route.total_distance_m)}
        </Text>
      </View>

      {/* Leg strip */}
      <View className="mb-2 flex-row items-center gap-1">
        {route.legs.map((leg, i) => (
          <View
            key={i}
            className={`h-1.5 rounded-full ${leg.mode === 'bus' ? 'bg-[#09A6F3]' : 'bg-gray-300'}`}
            style={{ flex: leg.distance_m, minWidth: 6 }}
          />
        ))}
      </View>

      {/* Bus lines + type badge */}
      <View className="flex-row flex-wrap items-center gap-2">
        {lines.map((name) => (
          <View key={name} className="flex-row items-center rounded-lg bg-[#DDF6FF] px-2 py-0.5">
            <Feather name="truck" size={11} color={BLUE} />
            <Text className="ml-1 text-xs font-semibold text-[#09A6F3]">{name}</Text>
          </View>
        ))}
        <View
          className={`rounded-lg px-2 py-0.5 ${trip.type === 'commute' ? 'bg-green-50' : 'bg-amber-50'}`}
        >
          <Text
            className={`text-xs font-medium ${trip.type === 'commute' ? 'text-green-600' : 'text-amber-600'}`}
          >
            {trip.type === 'commute' ? 'Recurrente' : 'Solo hoy'}
          </Text>
        </View>
      </View>
    </View>
  );
}
