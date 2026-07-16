import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { bestWindow } from '../../constants/trip-data';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

export function BestWindowCard() {
  const total = bestWindow.dayEnd - bestWindow.dayStart;
  const left = ((bestWindow.from - bestWindow.dayStart) / total) * 100;
  const width = ((bestWindow.to - bestWindow.from) / total) * 100;

  return (
    <View style={styles.card}>
      <View style={styles.spine} />

      <View style={styles.inner}>
        <View style={styles.head}>
          <View style={styles.eyebrowRow}>
            <Ionicons name="time-outline" size={13} color={Palette.primary} />
            <Text style={styles.eyebrow}>BEST WINDOW TODAY</Text>
          </View>
          <Pressable style={styles.cta}>
            <Text style={styles.ctaText}>Go now</Text>
          </Pressable>
        </View>

        <Text style={styles.window}>
          {bestWindow.start} – {bestWindow.end}
        </Text>

        <View style={styles.track}>
          <View style={[styles.fill, { left: `${left}%`, width: `${width}%` }]} />
        </View>

        <View style={styles.ticks}>
          {bestWindow.ticks.map((tick) => (
            <Text key={tick} style={styles.tick}>
              {tick}
            </Text>
          ))}
        </View>

        <Text style={styles.reasons}>{bestWindow.reasons.join(' · ')}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    marginHorizontal: Space.lg,
    marginTop: -64,
    borderRadius: Radius.xl,
    backgroundColor: Palette.surface,
    overflow: 'hidden',
    ...Shadow.card,
  },
  spine: {
    width: 4,
    backgroundColor: Palette.primary,
  },
  inner: {
    flex: 1,
    padding: Space.lg,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  eyebrowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  eyebrow: {
    ...Type.eyebrow,
    color: Palette.primary,
  },
  cta: {
    paddingHorizontal: Space.md,
    paddingVertical: 6,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primarySoft,
  },
  ctaText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primaryDeep,
  },
  window: {
    ...Type.window,
    color: Palette.text,
    marginTop: Space.sm,
  },
  track: {
    height: 5,
    borderRadius: Radius.pill,
    backgroundColor: Palette.borderSoft,
    marginTop: Space.lg,
  },
  fill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primary,
  },
  ticks: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: Space.sm,
  },
  tick: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
  reasons: {
    ...Type.body,
    color: Palette.primary,
    marginTop: Space.lg,
  },
});
