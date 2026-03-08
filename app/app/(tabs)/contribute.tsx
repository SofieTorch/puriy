import Header from '@/components/header';
import { styles } from '@/styles/index';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '@react-navigation/native';
import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

type Segment = 'lineas' | 'mapa';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const [segment, setSegment] = useState<Segment>('lineas');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  return (
    <View style={[styles.container, { paddingTop: insets.top, backgroundColor: colors.background }]}>
      {/* Header */}
      <Header title="Explorar" />
      <View style={styles.header}>
        <View style={styles.segmentedControl}>
          <Pressable
            style={[
              styles.segment,
              segment === 'lineas' && styles.segmentActive,
            ]}
            onPress={() => setSegment('lineas')}
          >
            <Text
              style={[
                styles.segmentText,
                segment === 'lineas' && styles.segmentTextActive,
              ]}
            >
              Líneas
            </Text>
          </Pressable>
          <Pressable
            style={[
              styles.segment,
              segment === 'mapa' && styles.segmentActive,
            ]}
            onPress={() => setSegment('mapa')}
          >
            <Text
              style={[
                styles.segmentText,
                segment === 'mapa' && styles.segmentTextActive,
              ]}
            >
              Mapa
            </Text>
          </Pressable>
        </View>
      </View>

      {/* From / To card */}
      <View style={styles.searchCardWrapper}>
        <View style={styles.searchCard}>
          <View style={styles.searchInputRow}>
            <View>
              <TextInput
                style={styles.searchInput}
                placeholder="Origen"
                placeholderTextColor="#9CA3AF"
                value={from}
                onChangeText={setFrom}
              />
            </View>
            <View>
              <TextInput
                style={styles.searchInput}
                placeholder="Destino"
                placeholderTextColor="#9CA3AF"
                value={to}
                onChangeText={setTo}
              />
            </View>
          </View>
        </View>
      </View>

      <View style={styles.linesCard}>
        <Text style={styles.linesCardTitle}>Líneas cercanas</Text>
        <View style={styles.tableHeader}>
          <View style={styles.tableCellIcon} />
          <Text style={[styles.tableCell, styles.tableHeaderText]}>Línea</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText]}>Dirección</Text>
        </View>
        {/* Placeholder rows */}
        <View style={styles.tableRow}>
          <View style={styles.tableCellIcon}>
            <MaterialCommunityIcons name="bus" size={22} color="#09A6F3" />
          </View>
          <Text style={styles.tableCell} numberOfLines={1}>150 Univalle</Text>
          <Text style={styles.tableCell} numberOfLines={1}>Tiquipaya</Text>
        </View>
        <View style={styles.tableRow}>
          <View style={styles.tableCellIcon}>
            <MaterialCommunityIcons name="bus" size={22} color="#09A6F3" />
          </View>
          <Text style={styles.tableCell} numberOfLines={1}>150</Text>
          <Text style={styles.tableCell} numberOfLines={1}>Reducto</Text>
        </View>
        <View style={styles.tableRow}>
          <View style={styles.tableCellIcon}>
            <MaterialCommunityIcons name="train" size={22} color="#6B7280" />
          </View>
          <Text style={styles.tableCell} numberOfLines={1}>150</Text>
          <Text style={styles.tableCell} numberOfLines={1}>Cancha</Text>
        </View>
      </View>
    </View>
  );
}

