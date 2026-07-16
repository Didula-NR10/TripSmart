import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Destination, destinations } from '../../constants/trip-data';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

function Tile({ place }: { place: Destination }) {
  const primary = place.tagTone === 'primary';

  return (
    <Pressable style={styles.tile}>
      <View style={styles.frame}>
        <Image source={place.image} style={StyleSheet.absoluteFill} resizeMode="cover" />
        <LinearGradient
          colors={['rgba(9, 34, 38, 0.35)', 'transparent', 'rgba(9, 34, 38, 0.65)']}
          locations={[0, 0.5, 1]}
          style={StyleSheet.absoluteFill}
        />

        <View style={styles.frameTop}>
          <View style={[styles.tag, primary ? styles.tagPrimary : styles.tagNeutral]}>
            <Text style={[styles.tagText, primary && styles.tagTextPrimary]}>{place.tag}</Text>
          </View>
          <Ionicons name="bookmark-outline" size={15} color={Palette.onDark} />
        </View>

        <Text style={styles.temp}>{place.temp}°</Text>
      </View>

      <Text style={styles.name}>{place.name}</Text>
      <Text style={styles.district}>{place.district}</Text>
    </Pressable>
  );
}

export function DestinationGrid() {
  return (
    <View style={styles.grid}>
      {destinations.map((place) => (
        <Tile key={place.key} place={place} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Space.md,
  },
  tile: {
    flexGrow: 1,
    flexBasis: '46%',
  },
  frame: {
    height: 122,
    borderRadius: Radius.lg,
    overflow: 'hidden',
    padding: Space.sm,
    justifyContent: 'space-between',
    backgroundColor: Palette.neutralChip,
    ...Shadow.soft,
  },
  frameTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  tag: {
    paddingHorizontal: Space.sm,
    paddingVertical: 3,
    borderRadius: Radius.pill,
  },
  tagPrimary: {
    backgroundColor: Palette.primary,
  },
  tagNeutral: {
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
  },
  tagText: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.text,
  },
  tagTextPrimary: {
    color: Palette.onDark,
  },
  temp: {
    ...Type.title,
    color: Palette.onDark,
    alignSelf: 'flex-end',
  },
  name: {
    ...Type.label,
    color: Palette.text,
    marginTop: Space.sm,
  },
  district: {
    ...Type.caption,
    color: Palette.textMuted,
    marginTop: 1,
  },
});
