import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Zone } from '../../constants/geofences';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export function ZoneModal({ zone, onClose }: { zone: Zone | null; onClose: () => void }) {
  if (!zone) return null;
  const restricted = zone.kind === 'restricted';
  const accent = restricted ? Palette.danger : Palette.primary;
  const tint = restricted ? Palette.dangerSoft : Palette.primaryTint;

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.scrim}>
        <View style={styles.card}>
          <View style={[styles.badge, { backgroundColor: tint }]}>
            <Ionicons
              name={restricted ? 'warning' : 'hand-left-outline'}
              size={22}
              color={accent}
            />
          </View>

          <Text style={styles.kind}>
            {restricted ? 'RESTRICTED ZONE' : 'SACRED SITE'}
          </Text>
          <Text style={styles.name}>{zone.name}</Text>

          <ScrollView style={styles.rules} showsVerticalScrollIndicator={false}>
            {zone.rules.map((rule) => (
              <View key={rule} style={styles.rule}>
                <View style={[styles.bullet, { backgroundColor: accent }]} />
                <Text style={styles.ruleText}>{rule}</Text>
              </View>
            ))}
          </ScrollView>

          <Pressable style={[styles.ack, { backgroundColor: accent }]} onPress={onClose}>
            <Text style={styles.ackText}>I understand</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
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
