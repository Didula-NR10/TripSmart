import { Image, ImageSourcePropType, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

/**
 * PageHero — the light, full-bleed banner header shared by Local Guide, Route
 * Intelligence and Ground Reports: a decorative photo fades into the canvas
 * from the top-right, with an optional icon badge, a big bold title and a
 * subtitle sitting on top of the clean (unobstructed) left side of it.
 *
 * Rendered as the first child of a screen's ScrollView; the negative margins
 * cancel that ScrollView's own padding so the photo can bleed edge-to-edge.
 */
export function PageHero({
  icon,
  title,
  subtitle,
  image,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  image: ImageSourcePropType;
}) {
  return (
    <View style={styles.wrap}>
      <Image source={image} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <LinearGradient
        colors={[Palette.canvas, Palette.canvas, 'rgba(245, 248, 249, 0.55)', 'transparent']}
        locations={[0, 0.38, 0.58, 1]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={StyleSheet.absoluteFill}
      />
      <LinearGradient
        colors={['transparent', 'rgba(245, 248, 249, 0.65)', Palette.canvas]}
        locations={[0.35, 0.7, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={styles.content}>
        {icon ? (
          <View style={styles.badge}>
            <Ionicons name={icon} size={22} color={Palette.onDark} />
          </View>
        ) : null}
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.subtitle}>{subtitle}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 232,
    marginTop: -Space.lg,
    marginHorizontal: -Space.lg,
    marginBottom: Space.xl,
    backgroundColor: Palette.canvas,
    overflow: 'hidden',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: Space.lg,
  },
  badge: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Palette.primaryDeep,
    marginBottom: Space.md,
  },
  title: {
    fontFamily: Type.title.fontFamily,
    fontSize: 34,
    letterSpacing: -0.8,
    color: Palette.text,
  },
  subtitle: {
    ...Type.body,
    fontSize: 13,
    lineHeight: 18,
    color: Palette.textMuted,
    marginTop: Space.sm,
    maxWidth: '78%',
  },
});
