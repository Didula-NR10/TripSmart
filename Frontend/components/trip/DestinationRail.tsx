import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { destinations } from '../../constants/trip-data';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export function DestinationRail() {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.rail}
    >
      {destinations.map((place) => (
        <Pressable key={place.key} style={styles.card}>
          <LinearGradient
            colors={[place.hue, Palette.surfaceInset]}
            start={{ x: 0.2, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.canvas}
          >
            <View style={styles.grade}>
              <Text style={styles.gradeText}>{place.grade}</Text>
            </View>
          </LinearGradient>

          <View style={styles.meta}>
            <Text style={styles.name}>{place.name}</Text>
            <View style={styles.region}>
              <Ionicons name="location-outline" size={10} color={Palette.textDim} />
              <Text style={styles.regionText}>{place.region}</Text>
            </View>
          </View>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  rail: {
    gap: Space.md,
    paddingRight: Space.lg,
  },
  card: {
    width: 132,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Palette.border,
    backgroundColor: Palette.surface,
    overflow: 'hidden',
  },
  canvas: {
    height: 92,
    padding: Space.sm,
    alignItems: 'flex-end',
  },
  grade: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: Radius.sm,
    backgroundColor: 'rgba(10, 15, 23, 0.6)',
    borderWidth: 1,
    borderColor: Palette.accentEdge,
  },
  gradeText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 10,
    color: Palette.accent,
  },
  meta: {
    padding: Space.md,
    gap: 3,
  },
  name: {
    ...Type.label,
    color: Palette.text,
  },
  region: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  regionText: {
    ...Type.caption,
    fontSize: 11,
    color: Palette.textDim,
  },
});
