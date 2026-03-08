import React, { useEffect, useState } from 'react';
import { Image, Text, View } from 'react-native';

import { isServerReachable } from '@/services/api';
import { subscribeRecordingStatus } from '@/services/recording-status';
import { subscribeSyncStatus } from '@/services/sync';

const POLL_MS = 15000;

export default function Header({ title }: { title: string }) {
  const [isOnline, setIsOnline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  useEffect(() => {
    let mounted = true;

    const poll = async () => {
      const reachable = await isServerReachable();
      if (mounted) setIsOnline(reachable);
    };

    poll();
    const interval = setInterval(poll, POLL_MS);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    return subscribeSyncStatus(setIsSyncing);
  }, []);

  useEffect(() => {
    return subscribeRecordingStatus(setIsRecording);
  }, []);

  return (
    <View className="relative justify-center bg-[#09A6F3] p-4">
      <View className="flex-row items-center justify-between">
        <View
          className="flex-row items-center gap-1.5 rounded-xl bg-white/20 px-2.5 py-1"
        >
          <View
            className={`h-2 w-2 rounded-xl ${isRecording ? 'bg-red-500' : isSyncing ? 'bg-orange-500' : isOnline ? 'bg-green-500' : 'bg-gray-400'}`}
          />
          <Text className="text-xs font-semibold text-white">
            {isRecording ? 'grabando...' : isSyncing ? 'sincronizando...' : isOnline ? 'online' : 'offline'}
          </Text>
        </View>
        <View>
          <Image source={require('@/assets/travel.png')} className="h-8 w-8" />
        </View>
      </View>
      <View pointerEvents="none" className="absolute inset-0 items-center justify-center">
        <Text className="text-xl font-medium text-white">{title}</Text>
      </View>
    </View>
  );
}