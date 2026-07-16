import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  Specialty,
  SpecialtyCategory,
  specialtyCategoryLabel,
} from '../../constants/specialties';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const categoryIcon: Record<SpecialtyCategory, keyof typeof Ionicons.glyphMap> = {
  food: 'restaurant-outline',
  drink: 'cafe-outline',
  dessert: 'ice-cream-outline',
  craft: 'color-palette-outline',
  gem_mineral: 'diamond-outline',
  agri_produce: 'leaf-outline',
  textile: 'shirt-outline',
};

const INITIAL_COUNT = 6;

/** In the All Sri Lanka view each item carries the district it belongs to. */
type TaggedSpecialty = Specialty & { district?: string };

function SpecialtyRow({ item, onPress }: { item: TaggedSpecialty; onPress: () => void }) {
  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={styles.rowIcon}>
        <Ionicons name={categoryIcon[item.category]} size={15} color={Palette.primary} />
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle} numberOfLines={2}>
          {item.name}
        </Text>
        <Text style={styles.rowKind}>
          {specialtyCategoryLabel[item.category]}
          {item.district ? ` · ${item.district}` : ''}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={15} color={Palette.textDim} />
    </Pressable>
  );
}

export function SpecialtyGuide({
  items,
  districtName,
}: {
  items: TaggedSpecialty[];
  /** Name of the filtered district, or null for the All Sri Lanka view. */
  districtName: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const [open, setOpen] = useState<TaggedSpecialty | null>(null);

  if (items.length === 0) return null;

  const shown = expanded ? items : items.slice(0, INITIAL_COUNT);

  return (
    <View style={styles.card}>
      <View style={styles.summary}>
        <Ionicons name="sparkles-outline" size={14} color={Palette.textMuted} />
        <Text style={styles.summaryText}>
          {districtName ?? 'Sri Lanka'} is famous for {items.length} local specialties —
          food, crafts and more. Tap any for details.
        </Text>
      </View>

      {shown.map((item, i) => (
        <View key={`${item.district ?? ''}-${item.name}`} style={i > 0 && styles.divider}>
          <SpecialtyRow item={item} onPress={() => setOpen(item)} />
        </View>
      ))}

      {items.length > INITIAL_COUNT ? (
        <Pressable style={styles.toggle} onPress={() => setExpanded((v) => !v)}>
          <Text style={styles.toggleText}>
            {expanded ? 'Show fewer' : `Show all ${items.length}`}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={14}
            color={Palette.primary}
          />
        </Pressable>
      ) : null}

      {/* ── detail modal ──────────────────────────────────────────────── */}
      <Modal
        visible={open !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setOpen(null)}
      >
        {open ? (
          <View style={styles.scrim}>
            <View style={styles.sheet}>
              <View style={styles.sheetHead}>
                <View style={styles.badge}>
                  <Ionicons
                    name={categoryIcon[open.category]}
                    size={22}
                    color={Palette.primary}
                  />
                </View>
                <Pressable onPress={() => setOpen(null)} hitSlop={10}>
                  <Ionicons name="close" size={22} color={Palette.textMuted} />
                </Pressable>
              </View>

              <Text style={styles.kind}>
                {specialtyCategoryLabel[open.category].toUpperCase()} ·{' '}
                {open.district ?? districtName ?? 'Sri Lanka'}
              </Text>
              <Text style={styles.name}>{open.name}</Text>

              <ScrollView style={styles.detail} showsVerticalScrollIndicator={false}>
                <Text style={styles.detailText}>{open.description}</Text>
                <View style={styles.factRow}>
                  <Ionicons name="bulb-outline" size={14} color={Palette.warn} />
                  <Text style={styles.factText}>{open.notification_text}</Text>
                </View>
              </ScrollView>

              <Pressable style={styles.ack} onPress={() => setOpen(null)}>
                <Text style={styles.ackText}>Got it</Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <View />
        )}
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
  },
  summary: {
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: Space.sm,
    paddingBottom: Space.md,
  },
  summaryText: {
    ...Type.caption,
    color: Palette.textMuted,
    flex: 1,
    lineHeight: 15,
  },
  divider: {
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    paddingVertical: Space.md,
    paddingHorizontal: Space.sm,
  },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowBody: { flex: 1 },
  rowTitle: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
    lineHeight: 16,
  },
  rowKind: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    marginTop: 3,
  },
  toggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: Space.md,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  toggleText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
  },
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: Space.xl,
  },
  sheet: {
    width: '100%',
    maxHeight: '80%',
    backgroundColor: Palette.surface,
    borderRadius: Radius.xxl,
    padding: Space.xl,
  },
  sheetHead: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  badge: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.lg,
  },
  kind: {
    ...Type.eyebrow,
    color: Palette.textMuted,
  },
  name: {
    ...Type.title,
    color: Palette.text,
    marginTop: 4,
  },
  detail: {
    marginTop: Space.lg,
  },
  detailText: {
    ...Type.body,
    color: Palette.textMuted,
    lineHeight: 20,
    marginBottom: Space.md,
  },
  factRow: {
    flexDirection: 'row',
    gap: Space.sm,
    marginBottom: Space.md,
    alignItems: 'flex-start',
  },
  factText: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    flex: 1,
    lineHeight: 17,
  },
  ack: {
    marginTop: Space.lg,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    alignItems: 'center',
    backgroundColor: Palette.primary,
  },
  ackText: {
    ...Type.label,
    color: Palette.onDark,
  },
});
