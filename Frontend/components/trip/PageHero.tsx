import { ReactNode } from 'react';
import { Image, ImageSourcePropType, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

/**
 * PageHero — the light, full-bleed banner header shared by every tab (Local
 * Guide, Route Intelligence, Ground Reports, Profile): a decorative photo
 * fades into the canvas from the top-right, with an icon badge, a big bold
 * title and a subtitle sitting on top of the clean (unobstructed) left side
 * of it. `topRight` (e.g. Profile's settings/notification buttons) is
 * absolutely positioned so it never shifts where the badge/title sit —
 * every screen using this component gets the identical header height and
 * text position, so switching tabs never jumps.
 *
 * Rendered as the first child of a screen's ScrollView; the negative margins
 * cancel that ScrollView's own padding so the photo can bleed edge-to-edge.
 */
export function PageHero({
  icon,
  title,
  subtitle,
  image,
  topRight,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  image: ImageSourcePropType;
  topRight?: ReactNode;
}) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.wrap, { height: 232 + insets.top }]}>
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

      {/* The photo now bleeds behind the status bar (the screen's own
          SafeAreaView no longer reserves that space), so badge/title and
          topRight need the inset pushed back in here instead. */}
      {topRight ? (
        <View style={[styles.topRight, { top: Space.sm + insets.top }]}>{topRight}</View>
      ) : null}

      <View style={[styles.content, { paddingTop: 40 + insets.top }]}>
        <View style={styles.badge}>
          <Ionicons name={icon} size={22} color={Palette.onDark} />
        </View>
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
    justifyContent: 'flex-start',
    paddingTop: 40,
    paddingHorizontal: Space.lg,
  },
  topRight: {
    position: 'absolute',
    top: Space.sm,
    right: Space.lg,
    flexDirection: 'row',
    gap: Space.sm,
    zIndex: 2,
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
