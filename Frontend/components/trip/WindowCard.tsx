import { useState } from 'react';
import { LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ForecastCurve } from './ForecastCurve';
import { Prediction, Window } from '../../lib/engine';
import { Profile } from '../../constants/profiles';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

type Props = {
  prediction: Prediction;
  window: Window;
  grade: { letter: string; score: number };
  profile: Profile;
};

const fmt = (h: number) => {
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour}:00 ${suffix}`;
};

export function WindowCard({ prediction, window, grade, profile }: Props) {
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  return (
    <View style={styles.card}>
      <View style={styles.spine} />
      <View style={styles.inner}>
        <View style={styles.head}>
          <View style={styles.eyebrowRow}>
            <Ionicons name="time-outline" size={13} color={Palette.primary} />
            <Text style={styles.eyebrow}>BEST WINDOW TODAY</Text>
          </View>
          <View style={styles.grade}>
            <Text style={styles.gradeLetter}>{grade.letter}</Text>
          </View>
        </View>

        {window ? (
          <Text style={styles.window}>
            {fmt(window.from)} – {fmt(window.to)}
          </Text>
        ) : (
          <Text style={styles.window}>No clear window</Text>
        )}

        <Text style={styles.forWhom}>
          Scored for {profile.name} · {grade.score}/100
        </Text>

        <View style={styles.chart} onLayout={onLayout}>
          {width > 0 ? (
            <ForecastCurve hours={prediction.hours} width={width} window={window} />
          ) : null}
        </View>

        <Pressable style={styles.cta}>
          <Text style={styles.ctaText}>Go now</Text>
          <Ionicons name="arrow-forward" size={14} color={Palette.onDark} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    marginHorizontal: Space.lg,
    marginTop: -60,
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
  grade: {
    minWidth: 40,
    paddingHorizontal: Space.sm,
    paddingVertical: 3,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primarySoft,
    alignItems: 'center',
  },
  gradeLetter: {
    ...Type.label,
    color: Palette.primaryDeep,
  },
  window: {
    ...Type.window,
    color: Palette.text,
    marginTop: Space.sm,
  },
  forWhom: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 2,
  },
  chart: {
    marginTop: Space.lg,
  },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: Space.lg,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
  },
  ctaText: {
    ...Type.label,
    color: Palette.onDark,
  },
});
