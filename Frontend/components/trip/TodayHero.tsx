import { useEffect, useRef, useState } from 'react';
import { Animated, Image, StyleSheet, Text, View, Pressable } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { District } from '../../constants/districts';
import { heroForDistrict } from '../../constants/district-hero';
import { HourPrediction } from '../../lib/engine';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

type Props = {
  district: District;
  now: HourPrediction;
  offline: boolean;
  previewLabel?: string;
  onPressDistrict: () => void;
  onPressNotifications?: () => void;
  unreadNotifications?: number;
};

function Metric({ icon, value }: { icon: keyof typeof Ionicons.glyphMap; value: string }) {
  return (
    <View style={styles.metric}>
      <Ionicons name={icon} size={13} color={Palette.onDarkMuted} />
      <Text style={styles.metricText}>{value}</Text>
    </View>
  );
}

export function TodayHero({
  district,
  now,
  offline,
  previewLabel,
  onPressDistrict,
  onPressNotifications,
  unreadNotifications = 0,
}: Props) {
  const insets = useSafeAreaInsets();
  const date = new Date();
  const line = `${date.toLocaleDateString('en-US', { weekday: 'long' })} · ${date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} · ${district.province}${previewLabel ? ` · ${previewLabel}` : ''}`;

  const hero = heroForDistrict(district.key);

  // A short crossfade whenever the district (and so the photo) changes,
  // rather than the new landmark photo just popping in.
  const fade = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    fade.setValue(0);
    Animated.timing(fade, { toValue: 1, duration: 380, useNativeDriver: true }).start();
  }, [hero.url, fade]);

  return (
    <View style={styles.wrap}>
      <Animated.Image
        key={hero.url}
        source={{ uri: hero.url }}
        style={[StyleSheet.absoluteFill, { opacity: fade }]}
        resizeMode="cover"
      />
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
            <Pressable
              style={styles.iconButton}
              onPress={onPressNotifications}
              accessibilityLabel="Notifications"
            >
              <Ionicons name="notifications-outline" size={17} color={Palette.onDark} />
              {unreadNotifications > 0 ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>
                    {unreadNotifications > 9 ? '9+' : unreadNotifications}
                  </Text>
                </View>
              ) : null}
            </Pressable>
          )}
        </View>

        <View style={styles.readout}>
          <View style={styles.landmarkRow}>
            <Ionicons name="camera-outline" size={11} color={Palette.onDarkMuted} />
            <Text style={styles.landmark}>{hero.landmark}</Text>
          </View>
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
  badge: {
    position: 'absolute',
    top: -3,
    right: -3,
    minWidth: 16,
    height: 16,
    paddingHorizontal: 3,
    borderRadius: Radius.pill,
    backgroundColor: Palette.danger,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: Palette.primaryDeep,
  },
  badgeText: {
    ...Type.caption,
    fontSize: 8,
    fontWeight: '700',
    color: Palette.onDark,
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
  landmarkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  landmark: {
    ...Type.caption,
    fontSize: 10,
    letterSpacing: 0.3,
    color: Palette.onDarkMuted,
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
