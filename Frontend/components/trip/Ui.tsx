import { Pressable, StyleSheet, Text, View, ViewProps } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

export function Card({ style, ...rest }: ViewProps) {
  return <View style={[styles.card, style]} {...rest} />;
}

export function SectionHeader({
  title,
  action,
  onPress,
}: {
  title: string;
  action?: string;
  onPress?: () => void;
}) {
  return (
    <View style={styles.headerRow}>
      <Text style={styles.headerTitle}>{title}</Text>
      {action ? (
        <Pressable style={styles.headerAction} onPress={onPress} hitSlop={8}>
          <Text style={styles.headerActionText}>{action}</Text>
          <Ionicons name="chevron-forward" size={13} color={Palette.primary} />
        </Pressable>
      ) : null}
    </View>
  );
}

export function ScreenTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <View style={styles.screenTitle}>
      <Text style={styles.screenTitleText}>{title}</Text>
      <Text style={styles.screenSubtitle}>{subtitle}</Text>
    </View>
  );
}

type BannerTone = 'primary' | 'warn' | 'danger';

export function Banner({
  tone,
  icon,
  title,
  body,
  action,
  onPress,
}: {
  tone: BannerTone;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  body: string;
  action?: string;
  onPress?: () => void;
}) {
  const skin = {
    primary: { bg: Palette.primaryTint, fg: Palette.primaryDeep, rule: Palette.primary },
    warn: { bg: Palette.warnSoft, fg: '#7A5A12', rule: Palette.warn },
    danger: { bg: Palette.dangerSoft, fg: '#7E2A20', rule: Palette.danger },
  }[tone];

  return (
    <Pressable
      style={[styles.banner, { backgroundColor: skin.bg, borderLeftColor: skin.rule }]}
      onPress={onPress}
    >
      <Ionicons name={icon} size={17} color={skin.rule} style={styles.bannerIcon} />
      <View style={styles.bannerBody}>
        <Text style={[styles.bannerTitle, { color: skin.fg }]}>{title}</Text>
        <Text style={[styles.bannerText, { color: skin.fg }]}>{body}</Text>
        {action ? <Text style={[styles.bannerAction, { color: skin.rule }]}>{action}</Text> : null}
      </View>
    </Pressable>
  );
}

export function Pill({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.pill, active ? styles.pillOn : styles.pillOff]}
    >
      <Text style={[styles.pillText, active && styles.pillTextOn]}>{label}</Text>
    </Pressable>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    padding: Space.lg,
    ...Shadow.soft,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Space.md,
  },
  headerTitle: {
    ...Type.heading,
    color: Palette.text,
  },
  headerAction: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerActionText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
  },
  screenTitle: {
    marginBottom: Space.xl,
  },
  screenTitleText: {
    fontFamily: Type.title.fontFamily,
    fontSize: 26,
    letterSpacing: -0.6,
    color: Palette.text,
  },
  screenSubtitle: {
    ...Type.body,
    color: Palette.textMuted,
    marginTop: 3,
  },
  banner: {
    flexDirection: 'row',
    borderRadius: Radius.md,
    borderLeftWidth: 3,
    padding: Space.md,
    gap: Space.md,
  },
  bannerIcon: {
    marginTop: 1,
  },
  bannerBody: {
    flex: 1,
  },
  bannerTitle: {
    ...Type.label,
  },
  bannerText: {
    ...Type.body,
    fontSize: 12,
    marginTop: 2,
    opacity: 0.9,
  },
  bannerAction: {
    ...Type.label,
    fontSize: 12,
    marginTop: Space.sm,
  },
  pill: {
    paddingHorizontal: Space.md,
    paddingVertical: 7,
    borderRadius: Radius.pill,
    borderWidth: 1,
  },
  pillOff: {
    backgroundColor: Palette.surface,
    borderColor: Palette.border,
  },
  pillOn: {
    backgroundColor: Palette.primary,
    borderColor: Palette.primary,
  },
  pillText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.textMuted,
  },
  pillTextOn: {
    color: Palette.onDark,
  },
  empty: {
    padding: Space.xl,
    alignItems: 'center',
  },
  emptyText: {
    ...Type.body,
    color: Palette.textDim,
    textAlign: 'center',
  },
});
