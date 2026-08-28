import { Pressable, StyleSheet, Text, View, ViewProps } from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

export function Card({ style, ...rest }: ViewProps) {
  return <View style={[styles.card, style]} {...rest} />;
}

type IconLib = 'ion' | 'mci';

export function SectionHeader({
  title,
  icon,
  iconLib = 'ion',
  iconTone = 'primary',
  action,
  actionTone = 'primary',
  onPress,
}: {
  title: string;
  icon?: string;
  iconLib?: IconLib;
  iconTone?: 'primary' | 'danger';
  action?: string;
  actionTone?: 'primary' | 'danger';
  onPress?: () => void;
}) {
  const tone = { primary: Palette.primary, danger: Palette.danger }[iconTone];
  const actionColor = { primary: Palette.primary, danger: Palette.danger }[actionTone];

  return (
    <View style={styles.headerRow}>
      <View style={styles.headerLeft}>
        {icon ? (
          <View style={[styles.headerIcon, { backgroundColor: tone + '22' }]}>
            {iconLib === 'mci' ? (
              <MaterialCommunityIcons name={icon as any} size={16} color={tone} />
            ) : (
              <Ionicons name={icon as any} size={16} color={tone} />
            )}
          </View>
        ) : null}
        <Text style={styles.headerTitle}>{title}</Text>
      </View>
      {action ? (
        <Pressable style={styles.headerAction} onPress={onPress} hitSlop={8}>
          <Text style={[styles.headerActionText, { color: actionColor }]}>{action}</Text>
          <Ionicons name="chevron-forward" size={13} color={actionColor} />
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
  decorative = true,
}: {
  tone: BannerTone;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  body: string;
  action?: string;
  onPress?: () => void;
  decorative?: boolean;
}) {
  const skin = {
    primary: { bg: Palette.primaryTint, fg: Palette.primaryDeep, rule: Palette.primary },
    warn: { bg: Palette.warnSoft, fg: '#7A5A12', rule: Palette.warn },
    danger: { bg: Palette.dangerSoft, fg: '#7E2A20', rule: Palette.danger },
  }[tone];

  return (
    <Pressable
      style={[styles.banner, { backgroundColor: skin.bg }]}
      onPress={onPress}
    >
      {decorative ? (
        <Ionicons
          name={icon}
          size={92}
          color={skin.rule}
          style={[styles.bannerWatermark, { opacity: 0.1 }]}
        />
      ) : null}
      <View style={[styles.bannerBadge, { backgroundColor: skin.rule }]}>
        <Ionicons name={icon} size={17} color={Palette.onDark} />
      </View>
      <View style={styles.bannerBody}>
        <Text style={[styles.bannerTitle, { color: skin.rule }]}>{title}</Text>
        <Text style={[styles.bannerText, { color: skin.fg }]}>{body}</Text>
        {action ? <Text style={[styles.bannerAction, { color: skin.rule }]}>{action}</Text> : null}
      </View>
    </Pressable>
  );
}

export function FilterRow({
  label,
  value,
  onPress,
}: {
  label: string;
  value: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.filterRow} onPress={onPress}>
      <View style={styles.filterIcon}>
        <Ionicons name="funnel-outline" size={15} color={Palette.primaryDeep} />
      </View>
      <View style={styles.filterBody}>
        <Text style={styles.filterLabel}>{label}</Text>
        <Text style={styles.filterValue}>{value}</Text>
      </View>
      <Ionicons name="chevron-down" size={16} color={Palette.textMuted} />
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
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    flex: 1,
  },
  headerIcon: {
    width: 30,
    height: 30,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
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
    borderRadius: Radius.lg,
    padding: Space.lg,
    gap: Space.md,
    overflow: 'hidden',
  },
  bannerWatermark: {
    position: 'absolute',
    right: -18,
    bottom: -18,
  },
  bannerBadge: {
    width: 36,
    height: 36,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bannerBody: {
    flex: 1,
  },
  bannerTitle: {
    ...Type.label,
    fontSize: 15,
  },
  bannerText: {
    ...Type.body,
    fontSize: 12,
    marginTop: 3,
    opacity: 0.9,
  },
  bannerAction: {
    ...Type.label,
    fontSize: 12,
    marginTop: Space.sm,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
  },
  filterIcon: {
    width: 30,
    height: 30,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterBody: { flex: 1 },
  filterLabel: {
    ...Type.caption,
    fontSize: 11,
    color: Palette.textMuted,
  },
  filterValue: {
    ...Type.label,
    fontSize: 15,
    color: Palette.text,
    marginTop: 1,
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
