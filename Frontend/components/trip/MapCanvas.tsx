import { StyleSheet, Text, View, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { districts, District } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const BOUNDS = { minLat: 5.85, maxLat: 9.9, minLng: 79.6, maxLng: 82.0 };

type Props = {
  selected: District;
  onPick: (lat: number, lng: number) => void;
};

export function MapCanvas({ selected, onPick }: Props) {
  const toXY = (lat: number, lng: number) => ({
    left: `${((lng - BOUNDS.minLng) / (BOUNDS.maxLng - BOUNDS.minLng)) * 100}%`,
    top: `${((BOUNDS.maxLat - lat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100}%`,
  });

  return (
    <View style={styles.canvas}>
      <View style={styles.notice}>
        <Ionicons name="information-circle-outline" size={13} color={Palette.textMuted} />
        <Text style={styles.noticeText}>
          Schematic view. Google Maps requires a development build.
        </Text>
      </View>

      {districts.map((d) => {
        const pos = toXY(d.lat, d.lng);
        const on = d.key === selected.key;
        return (
          <Pressable
            key={d.key}
            onPress={() => onPick(d.lat, d.lng)}
            style={[styles.dot, pos as any, on && styles.dotOn]}
          >
            {on ? <View style={styles.halo} /> : null}
          </Pressable>
        );
      })}

      <View style={styles.legend}>
        <Ionicons name="location" size={13} color={Palette.primary} />
        <Text style={styles.legendText}>{selected.name}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  canvas: {
    height: 300,
    borderRadius: Radius.xl,
    backgroundColor: Palette.primaryTint,
    borderWidth: 1,
    borderColor: Palette.border,
    overflow: 'hidden',
  },
  notice: {
    position: 'absolute',
    top: Space.md,
    left: Space.md,
    right: Space.md,
    zIndex: 5,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: Palette.surface,
    borderRadius: Radius.sm,
    paddingHorizontal: Space.sm,
    paddingVertical: 6,
  },
  noticeText: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
    flex: 1,
  },
  dot: {
    position: 'absolute',
    width: 10,
    height: 10,
    marginLeft: -5,
    marginTop: -5,
    borderRadius: Radius.pill,
    backgroundColor: Palette.textDim,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dotOn: {
    backgroundColor: Palette.primary,
  },
  halo: {
    position: 'absolute',
    width: 26,
    height: 26,
    borderRadius: Radius.pill,
    borderWidth: 2,
    borderColor: Palette.primary,
    opacity: 0.4,
  },
  legend: {
    position: 'absolute',
    bottom: Space.md,
    left: Space.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Palette.surface,
    paddingHorizontal: Space.md,
    paddingVertical: 7,
    borderRadius: Radius.pill,
  },
  legendText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
  },
});
