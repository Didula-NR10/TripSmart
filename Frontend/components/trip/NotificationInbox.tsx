/**
 * NotificationInbox — the bell button's target: an in-app list of every
 * notification the app has fired (district entry, laws/specialties, ground
 * reports). Exists because expo-notifications has no tray on web and Expo Go
 * users don't always see the OS panel, so there needs to be a reliable place
 * to answer "what did I just get notified about".
 */
import { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  NotificationEntry,
  getNotificationHistory,
  markAllNotificationsRead,
  subscribeNotificationHistory,
} from '../../lib/notify';
import { districtByKey } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const kindIcon: Record<NotificationEntry['kind'], keyof typeof Ionicons.glyphMap> = {
  district: 'shield-checkmark-outline',
  report: 'chatbubbles-outline',
};

const ago = (at: number) => {
  const mins = Math.max(0, Math.round((Date.now() - at) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
};

export function NotificationInbox({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const [entries, setEntries] = useState<NotificationEntry[]>([]);

  // Stay live while mounted so a notification firing on another tab updates the list.
  useEffect(() => {
    getNotificationHistory().then(setEntries);
    return subscribeNotificationHistory(setEntries);
  }, []);

  // Opening the inbox is what clears the unread badge.
  useEffect(() => {
    if (visible) markAllNotificationsRead();
  }, [visible]);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.scrim}>
        <View style={styles.sheet}>
          <View style={styles.grabber} />
          <View style={styles.head}>
            <Text style={styles.title}>Notifications</Text>
            <Pressable onPress={onClose} hitSlop={10} accessibilityLabel="Close notifications">
              <Ionicons name="close" size={20} color={Palette.textMuted} />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} style={styles.list}>
            {entries.length === 0 ? (
              <View style={styles.empty}>
                <Ionicons name="notifications-off-outline" size={22} color={Palette.textDim} />
                <Text style={styles.emptyText}>
                  Nothing yet. Move around with location on in the Culture tab and you'll see
                  local rules, specialties, and ground reports here as you enter districts.
                </Text>
              </View>
            ) : (
              entries.map((e) => {
                const district = districtByKey(e.districtKey);
                return (
                  <View key={e.id} style={styles.row}>
                    <View
                      style={[
                        styles.icon,
                        e.kind === 'report' ? styles.iconReport : styles.iconDistrict,
                      ]}
                    >
                      <Ionicons
                        name={kindIcon[e.kind]}
                        size={15}
                        color={e.kind === 'report' ? Palette.primary : Palette.warn}
                      />
                    </View>
                    <View style={styles.rowBody}>
                      <Text style={styles.rowTitle}>{e.title}</Text>
                      <Text style={styles.rowText} numberOfLines={2}>
                        {e.body}
                      </Text>
                      <Text style={styles.rowMeta}>
                        {district?.name ?? e.districtKey} · {ago(e.at)}
                      </Text>
                    </View>
                  </View>
                );
              })
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    height: '75%',
    backgroundColor: Palette.surface,
    borderTopLeftRadius: Radius.xxl,
    borderTopRightRadius: Radius.xxl,
    paddingHorizontal: Space.xl,
    paddingBottom: Space.xl,
  },
  grabber: {
    alignSelf: 'center',
    width: 38,
    height: 4,
    borderRadius: Radius.pill,
    backgroundColor: Palette.border,
    marginTop: Space.md,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: Space.lg,
    marginBottom: Space.md,
  },
  title: {
    ...Type.title,
    color: Palette.text,
  },
  list: {
    flex: 1,
  },
  empty: {
    alignItems: 'center',
    gap: Space.md,
    paddingTop: Space.section,
    paddingHorizontal: Space.lg,
  },
  emptyText: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
  row: {
    flexDirection: 'row',
    gap: Space.md,
    paddingVertical: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.borderSoft,
  },
  icon: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconDistrict: {
    backgroundColor: Palette.warnSoft,
  },
  iconReport: {
    backgroundColor: Palette.primaryTint,
  },
  rowBody: {
    flex: 1,
  },
  rowTitle: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
    lineHeight: 16,
  },
  rowText: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 2,
    lineHeight: 16,
  },
  rowMeta: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    marginTop: 4,
  },
});
