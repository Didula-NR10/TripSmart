import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Banner } from './Ui';
import { LawEntry, RiskLevel, lawsDisclaimer, typeLabel } from '../../constants/laws';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

/** Severity → the same tones the advisory banners use. */
const riskTone = (risk: RiskLevel) =>
  (({ high: 'danger', medium: 'warn', low: 'primary' }) as const)[risk];

const riskSkin = (risk: RiskLevel) =>
  ({
    high: { tint: Palette.dangerSoft, accent: Palette.danger, label: 'HIGH RISK' },
    medium: { tint: Palette.warnSoft, accent: Palette.warn, label: 'MEDIUM RISK' },
    low: { tint: Palette.primaryTint, accent: Palette.primary, label: 'LOW RISK' },
  })[risk];

const typeIcon: Record<LawEntry['type'], keyof typeof Ionicons.glyphMap> = {
  law: 'shield-checkmark-outline',
  safety: 'warning-outline',
  custom: 'hand-left-outline',
  ethics: 'leaf-outline',
};

const INITIAL_COUNT = 6;

/** The pop-up: same layout as the zone advisory modal — badge, eyebrow,
 *  title, severity-colored bullets, "I understand". */
function LawModal({ law, onClose }: { law: LawEntry | null; onClose: () => void }) {
  if (!law) return null;
  const skin = riskSkin(law.risk_level);

  const bullets: string[] = [];
  if (law.explanation) bullets.push(law.explanation);
  if (law.penalty) bullets.push(`If ignored: ${law.penalty}`);
  bullets.push(
    law.districts.includes('ALL')
      ? 'Applies everywhere in Sri Lanka.'
      : `Applies in: ${law.districts.join(', ')}.`,
  );

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.scrim}>
        <View style={styles.card}>
          <View style={[styles.badge, { backgroundColor: skin.tint }]}>
            <Ionicons name={typeIcon[law.type]} size={22} color={skin.accent} />
          </View>

          <Text style={styles.kind}>
            {typeLabel[law.type].toUpperCase()} · {skin.label} · {law.category.toUpperCase()}
          </Text>
          <Text style={styles.name}>{law.title}</Text>

          <ScrollView style={styles.rules} showsVerticalScrollIndicator={false}>
            {bullets.map((rule) => (
              <View key={rule} style={styles.rule}>
                <View style={[styles.bullet, { backgroundColor: skin.accent }]} />
                <Text style={styles.ruleText}>{rule}</Text>
              </View>
            ))}
            <Text style={styles.modalDisclaimer}>{lawsDisclaimer}</Text>
          </ScrollView>

          <Pressable style={[styles.ack, { backgroundColor: skin.accent }]} onPress={onClose}>
            <Text style={styles.ackText}>I understand</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

export function LawGuide({
  laws,
  districtName,
}: {
  laws: LawEntry[];
  /** Name of the filtered district, or null for the All Sri Lanka view. */
  districtName: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const [open, setOpen] = useState<LawEntry | null>(null);

  const shown = expanded ? laws : laws.slice(0, INITIAL_COUNT);
  const localCount = districtName
    ? laws.filter((l) => !l.districts.includes('ALL')).length
    : 0;

  return (
    <View>
      <View style={styles.summary}>
        <Ionicons name="information-circle-outline" size={14} color={Palette.textMuted} />
        <Text style={styles.summaryText}>
          {districtName
            ? `${laws.length} rules apply here — ${localCount} specific to ${districtName}, ${
                laws.length - localCount
              } nationwide. Colors follow severity; tap to read the rules.`
            : `All ${laws.length} rules & customs across Sri Lanka, most severe first. Tap to read the rules.`}
        </Text>
      </View>

      <View style={styles.banners}>
        {shown.map((law) => (
          <Banner
            key={law.id}
            tone={riskTone(law.risk_level)}
            icon={typeIcon[law.type]}
            title={law.title}
            body={`${typeLabel[law.type]} · ${law.category}. Tap to read the rules.`}
            action="Read rules"
            onPress={() => setOpen(law)}
          />
        ))}
      </View>

      {laws.length > INITIAL_COUNT ? (
        <Pressable style={styles.toggle} onPress={() => setExpanded((v) => !v)}>
          <Text style={styles.toggleText}>
            {expanded ? 'Show fewer' : `Show all ${laws.length}`}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={14}
            color={Palette.primary}
          />
        </Pressable>
      ) : null}

      <Text style={styles.disclaimer}>{lawsDisclaimer}</Text>

      <LawModal law={open} onClose={() => setOpen(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  summary: {
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: 2,
    paddingBottom: Space.md,
  },
  summaryText: {
    ...Type.caption,
    color: Palette.textMuted,
    flex: 1,
    lineHeight: 15,
  },
  banners: {
    gap: Space.sm,
  },
  toggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: Space.md,
  },
  toggleText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
  },
  disclaimer: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    lineHeight: 13,
    paddingHorizontal: 2,
  },
  // ── modal (mirrors ZoneModal) ─────────────────────────────────────────
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: Space.xl,
  },
  card: {
    width: '100%',
    maxHeight: '76%',
    backgroundColor: Palette.surface,
    borderRadius: Radius.xxl,
    padding: Space.xl,
  },
  badge: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
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
  rules: {
    marginTop: Space.lg,
  },
  rule: {
    flexDirection: 'row',
    gap: Space.md,
    marginBottom: Space.md,
  },
  bullet: {
    width: 5,
    height: 5,
    borderRadius: Radius.pill,
    marginTop: 7,
  },
  ruleText: {
    ...Type.body,
    color: Palette.textMuted,
    flex: 1,
  },
  modalDisclaimer: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    lineHeight: 13,
    marginTop: Space.sm,
    marginBottom: Space.md,
    paddingTop: Space.md,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  ack: {
    marginTop: Space.sm,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    alignItems: 'center',
  },
  ackText: {
    ...Type.label,
    color: Palette.onDark,
  },
});
