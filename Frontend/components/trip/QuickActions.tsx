import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { quickActions } from '../../constants/trip-data';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const tones: Record<string, { fg: string; bg: string }> = {
  accent: { fg: Palette.accent, bg: Palette.accentGlow },
  cyan: { fg: Palette.cyan, bg: Palette.cyanGlow },
  warn: { fg: Palette.warn, bg: Palette.warnGlow },
};

export function QuickActions() {
  const router = useRouter();

  return (
    <View style={styles.grid}>
      {quickActions.map((action) => {
        const tone = tones[action.tone];
        return (
          <Pressable
            key={action.key}
            style={({ pressed }) => [styles.tile, pressed && styles.tilePressed]}
            onPress={() => router.push(action.route as never)}
          >
            <View style={[styles.iconWrap, { backgroundColor: tone.bg, borderColor: tone.fg }]}>
              <Ionicons name={action.icon as never} size={16} color={tone.fg} />
            </View>

            <Text style={styles.title}>
              <Text style={styles.bracket}>[ </Text>
              {action.title}
              <Text style={styles.bracket}> ]</Text>
            </Text>
            <Text style={styles.caption} numberOfLines={2}>
              {action.caption}
            </Text>

            <Ionicons
              name="arrow-forward"
              size={13}
              color={Palette.textDim}
              style={styles.arrow}
            />
          </Pressable>
        );
      })}
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
    minHeight: 122,
    padding: Space.lg,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Palette.border,
    backgroundColor: Palette.surface,
  },
  tilePressed: {
    borderColor: Palette.accentEdge,
    backgroundColor: Palette.surfaceRaised,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.md,
  },
  title: {
    ...Type.label,
    color: Palette.text,
  },
  bracket: {
    color: Palette.accent,
    fontFamily: Type.metric.fontFamily,
    fontSize: 11,
  },
  caption: {
    ...Type.caption,
    color: Palette.textDim,
    marginTop: 4,
    lineHeight: 16,
  },
  arrow: {
    position: 'absolute',
    right: Space.lg,
    bottom: Space.lg,
  },
});
