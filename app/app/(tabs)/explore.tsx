import Feather from '@expo/vector-icons/Feather';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import Header from '@/components/header';
import { Input, InputField, InputSlot } from '@/components/ui/input';

type Segment = 'lineas' | 'mapa';

const BLUE = '#09A6F3';
export default function ExploreScreen() {
  const [segment, setSegment] = useState<Segment>('lineas');
  const [currentLocation, setCurrentLocation] = useState('');
  const [destination, setDestination] = useState('');

  return (
    <SafeAreaView className="flex-1 bg-[#09A6F3]">
      <View className="flex-1 bg-white">
        <Header title="Explorar" />

        <View className="flex-1 px-5 pt-6">
          <View className="mb-7 flex-row rounded-2xl bg-[#DDF6FF] p-2">
            <Pressable
              className={`flex-1 items-center justify-center rounded-xl py-2 ${segment === 'lineas' ? 'bg-[#09A6F3]' : ''}`}
              onPress={() => setSegment('lineas')}
            >
              <Text className={`text-lg ${segment === 'lineas' ? 'text-white font-bold' : 'text-[#7DD1FF] font-normal'}`}>
                Líneas
              </Text>
            </Pressable>
            <Pressable
              className={`flex-1 items-center justify-center rounded-xl py-2 ${segment === 'mapa' ? 'bg-[#09A6F3]' : ''}`}
              onPress={() => setSegment('mapa')}
            >
              <Text className={`text-lg ${segment === 'mapa' ? 'text-white font-bold' : 'text-[#7DD1FF] font-normal'}`}>
                Mapa
              </Text>
            </Pressable>
          </View>

          <View className="mb-3">
            <Input variant="outline" size="xl" className="h-14 rounded-xl border-2 border-[#09A6F3] bg-white">
              <InputSlot className="pl-2">
                <Feather name="crosshair" size={24} color={BLUE} />
              </InputSlot>
              <InputField
                cursorColor={BLUE}
                placeholder="Punto de partida"
                placeholderTextColor={BLUE}
                value={currentLocation}
                onChangeText={setCurrentLocation}
              />
            </Input>
          </View>

          <View className="mb-3">
            <Input variant="outline" size="xl" className="h-14 rounded-xl border-2 border-[#09A6F3] bg-white">
              <InputSlot className="pl-2">
                <Feather name="target" size={24} color={BLUE} />
              </InputSlot>
              <InputField
                cursorColor={BLUE}
                placeholder="Destino"
                placeholderTextColor={BLUE}
                value={destination}
                onChangeText={setDestination}
              />
            </Input>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}
