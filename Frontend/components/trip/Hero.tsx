import { Image, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { conditions, heroImage, todayLine } from '../../constants/trip-data';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

function Metric({ icon, value }: { icon: keyof typeof Ionicons.glyphMap; value: string }) {
  return (
    <View style={styles.metric}>
      <Ionicons name={icon} size={13} color={Palette.onDarkMuted} />
      <Text style={styles.metricText}>{value}</Text>
    </View>
  );
}

export function Hero() {
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.wrap}>
      <Image source={heroImage} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <LinearGradient
        colors={[Palette.scrimTop, 'transparent', Palette.scrimBottom]}
        locations={[0, 0.42, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={[styles.content, { paddingTop: insets.top + Space.md }]}>
        <View style={styles.topRow}>
          <View style={styles.place}>
            <Ionicons name="location-outline" size={15} color={Palette.onDark} />
            <Text style={styles.placeText}>
              {conditions.city}, {conditions.country}
            </Text>
          </View>

          <View style={styles.actions}>
            <View style={styles.iconButton}>
              <Ionicons name="notifications-outline" size={17} color={Palette.onDark} />
              <View style={styles.badge} />
            </View>
            <View style={styles.avatar}>
              <Ionicons name="person" size={15} color={Palette.onDarkMuted} />
            </View>
          </View>
        </View>

        <View style={styles.readout}>
          <Text style={styles.date}>{todayLine()}</Text>

          <View style={styles.tempRow}>
            <Text style={styles.temp}>{conditions.temp}°</Text>
            <View style={styles.tempMeta}>
              <Text style={styles.summary}>{conditions.summary}</Text>
              <Text style={styles.feels}>Feels like {conditions.feelsLike}°</Text>
            </View>
          </View>

          <View style={styles.metrics}>
            <Metric icon="navigate-outline" value={conditions.wind} />
            <Metric icon="water-outline" value={conditions.humidity} />
            <Metric icon="eye-outline" value={conditions.visibility} />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 360,
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
  },
  placeText: {
    ...Type.label,
    color: Palette.onDark,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
  },
  iconButton: {
    width: 34,
    height: 34,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
  },
  badge: {
    position: 'absolute',
    top: 8,
    right: 9,
    width: 6,
    height: 6,
    borderRadius: Radius.pill,
    backgroundColor: Palette.warn,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.24)',
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
