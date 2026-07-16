import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { HourPrediction, Window } from '../../lib/engine';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

function glyph(h: HourPrediction): keyof typeof Ionicons.glyphMap {
  if (h.rain > 2) return 'rainy';
  if (h.rain > 0.4) return 'cloud';
  if (h.hour < 6 || h.hour > 18) return 'moon';
  return 'sunny';
}

const label = (h: number) => {
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour} ${suffix}`;
};

type Props = {
  hours: HourPrediction[];
  window: Window;
  selectedHour?: number;
  onSelectHour?: (hour: number) => void;
};

export function HourStrip({ hours, window, selectedHour, onSelectHour }: Props) {
  const slice = hours.filter((h) => h.hour >= 5 && h.hour <= 20);

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip}>
      {slice.map((h) => {
        const on = !!window && h.hour >= window.from && h.hour < window.to;
        const picked = selectedHour === h.hour;
        return (
          <Pressable
            key={h.hour}
            onPress={() => onSelectHour?.(h.hour)}
            style={[styles.chip, on ? styles.chipOn : styles.chipOff, picked && styles.chipPicked]}
          >
            <Text style={[styles.label, on && styles.labelOn]}>{label(h.hour)}</Text>
            <Ionicons name={glyph(h)} size={19} color={on ? Palette.onDark : Palette.warn} />
            <Text style={[styles.temp, on && styles.tempOn]}>{Math.round(h.temp)}°</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  strip: {
    gap: Space.sm,
    paddingRight: Space.lg,
  },
  chip: {
    width: 62,
    paddingVertical: Space.md,
    borderRadius: Radius.lg,
    alignItems: 'center',
    gap: Space.sm,
  },
  chipOff: {
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
  },
  chipOn: {
    backgroundColor: Palette.primary,
    ...Shadow.soft,
  },
  chipPicked: {
    borderWidth: 2,
    borderColor: Palette.text,
  },
  label: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
  },
  labelOn: {
    color: Palette.onDarkMuted,
  },
  temp: {
    ...Type.label,
    color: Palette.text,
  },
  tempOn: {
    color: Palette.onDark,
  },
});
