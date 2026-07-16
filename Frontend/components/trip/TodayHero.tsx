import { Image, StyleSheet, Text, View, Pressable } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { District } from '../../constants/districts';
import { HourPrediction } from '../../lib/engine';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const hero = { uri: 'https://images.unsplash.com/photo-1641149750086-b11cd21d1f60?w=1200&q=80' };

type Props = {
  district: District;
  now: HourPrediction;
  offline: boolean;
  previewLabel?: string;
  onPressDistrict: () => void;
};

function Metric({ icon, value }: { icon: keyof typeof Ionicons.glyphMap; value: string }) {
  return (
    <View style={styles.metric}>
      <Ionicons name={icon} size={13} color={Palette.onDarkMuted} />
      <Text style={styles.metricText}>{value}</Text>
    </View>
  );
}

export function TodayHero({ district, now, offline, previewLabel, onPressDistrict }: Props) {
  const insets = useSafeAreaInsets();
  const date = new Date();
  const line = `${date.toLocaleDateString('en-US', { weekday: 'long' })} · ${date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} · ${district.province}${previewLabel ? ` · ${previewLabel}` : ''}`;

  return (
    <View style={styles.wrap}>
      <Image source={hero} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <LinearGradient
        colors={[Palette.scrimTop, 'transparent', Palette.scrimBottom]}
        locations={[0, 0.4, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={[styles.content, { paddingTop: insets.top + Space.md }]}>
        <View style={styles.topRow}>
          <Pressable style={styles.place} onPress={onPressDistrict}>
            <Ionicons name="location-outline" size={15} color={Palette.onDark} />
            <Text style={styles.placeText}>{district.name} District</Text>
            <Ionicons name="chevron-down" size={14} color={Palette.onDark} />
          </Pressable>

          {offline ? (
            <View style={styles.cached}>
              <Ionicons name="cloud-offline-outline" size={12} color={Palette.onDark} />
              <Text style={styles.cachedText}>CACHED</Text>
            </View>
          ) : (
            <View style={styles.iconButton}>
              <Ionicons name="notifications-outline" size={17} color={Palette.onDark} />
            </View>
          )}
        </View>

        <View style={styles.readout}>
          <Text style={styles.date}>{line}</Text>

          <View style={styles.tempRow}>
            <Text style={styles.temp}>{Math.round(now.temp)}°</Text>
            <View style={styles.tempMeta}>
              <Text style={styles.summary}>
                {now.rain > 2 ? 'Rain' : now.rain > 0.4 ? 'Light showers' : 'Clear'}
              </Text>
              <Text style={styles.feels}>{district.zone} zone · {district.elevation} m</Text>
            </View>
          </View>

          <View style={styles.metrics}>
            <Metric icon="navigate-outline" value={`${now.wind} km/h`} />
            <Metric icon="water-outline" value={`${now.humidity}%`} />
            <Metric icon="rainy-outline" value={`${now.rain} mm`} />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 340,
    borderBottomLeftRadius: Radius.xxl,
    borderBottomRightRadius: Radius.xxl,
    overflow: 'hidden',
    backgroundColor: Palette.primaryDeep,
  },
  content: {
    flex: 1,
    paddingHorizontal: Space.xl,
    paddingBottom: Space.section,
    justifyContent: 'space-between',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  place: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(255, 255, 255, 0.16)',
    paddingHorizontal: Space.md,
    paddingVertical: 7,
    borderRadius: Radius.pill,
  },
  placeText: {
    ...Type.label,
    color: Palette.onDark,
  },
  iconButton: {
    width: 34,
    height: 34,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
  },
  cached: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: Space.md,
    paddingVertical: 7,
    borderRadius: Radius.pill,
  },
  cachedText: {
    ...Type.caption,
    fontSize: 10,
    letterSpacing: 1,
    color: Palette.onDark,
  },
  readout: {
    gap: Space.md,
  },
  date: {
    ...Type.caption,
    color: Palette.onDarkMuted,
  },
  tempRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
  },
  temp: {
    ...Type.display,
    color: Palette.onDark,
  },
  tempMeta: {
    paddingBottom: Space.sm,
  },
  summary: {
    ...Type.title,
    color: Palette.onDark,
  },
  feels: {
    ...Type.body,
    color: Palette.onDarkMuted,
    marginTop: 1,
    textTransform: 'capitalize',
  },
  metrics: {
    flexDirection: 'row',
    gap: Space.xl,
  },
  metric: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  metricText: {
    ...Type.body,
    color: Palette.onDarkMuted,
  },
});
