import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { hourly, HourSlot } from '../../constants/trip-data';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

const glyph: Record<HourSlot['icon'], keyof typeof Ionicons.glyphMap> = {
  sunny: 'sunny',
  partly: 'partly-sunny',
  cloud: 'cloud',
};

export function HourlyStrip() {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.strip}
    >
      {hourly.map((slot) => {
        const on = slot.active;
        return (
          <View key={slot.key} style={[styles.chip, on ? styles.chipOn : styles.chipOff]}>
            <Text style={[styles.label, on && styles.labelOn]}>{slot.label}</Text>
            <Ionicons
              name={glyph[slot.icon]}
              size={20}
              color={on ? Palette.onDark : Palette.warn}
            />
            <Text style={[styles.temp, on && styles.tempOn]}>{slot.temp}°</Text>
          </View>
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
