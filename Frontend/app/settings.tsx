/**
 * app/settings.tsx — account and app settings. Reached from Profile's
 * settings icon; not a tab, so it has its own back button rather than
 * living in the bottom bar (same pattern as app/journal.tsx).
 *
 * Every control here does something real:
 *   - Notifications toggle actually gates lib/notify.ts's OS scheduling.
 *   - Clear cached forecast data actually wipes the AsyncStorage entries
 *     lib/api.ts's cacheForecast() writes.
 *   - Delete account actually calls the backend and signs the device out.
 * Nothing here is a placeholder.
 */
import { ReactNode, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { clearAllCachedForecasts } from '../lib/api';
import { useAuth } from '../lib/auth';
import { getNotificationsEnabled, setNotificationsEnabled } from '../lib/notify';
import { Palette, Radius, Shadow, Space, Type } from '../constants/trip-theme';

function SettingsRow({
  icon,
  iconColor = Palette.primary,
  iconBg = Palette.primaryTint,
  title,
  subtitle,
  right,
  onPress,
  disabled,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  iconBg?: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onPress?: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      style={[styles.row, disabled && styles.rowDisabled]}
      onPress={onPress}
      disabled={!onPress || disabled}
    >
      <View style={[styles.rowIcon, { backgroundColor: iconBg }]}>
        <Ionicons name={icon} size={16} color={iconColor} />
      </View>
      <View style={styles.rowText}>
        <Text style={styles.rowTitle}>{title}</Text>
        {subtitle ? <Text style={styles.rowSubtitle}>{subtitle}</Text> : null}
      </View>
      {right}
    </Pressable>
  );
}

export default function SettingsScreen() {
  const auth = useAuth();
  const [notifsEnabled, setNotifsEnabled] = useState(true);
  const [notifsReady, setNotifsReady] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearedNotice, setClearedNotice] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getNotificationsEnabled().then((v) => {
      setNotifsEnabled(v);
      setNotifsReady(true);
    });
  }, []);

  const toggleNotifications = async (value: boolean) => {
    setNotifsEnabled(value); // optimistic — this is a local preference, not a network call
    await setNotificationsEnabled(value);
  };

  const clearCache = async () => {
    setClearing(true);
    setClearedNotice(false);
    try {
      await clearAllCachedForecasts();
      setClearedNotice(true);
      setTimeout(() => setClearedNotice(false), 2500);
    } finally {
      setClearing(false);
    }
  };

  const confirmDeleteAccount = () => {
    Alert.alert(
      'Delete your account?',
      'This permanently deletes your account, your travel journal, your notes, and signs you out everywhere. Ground reports you posted stay visible but no longer show as yours. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete account',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            try {
              await auth.deleteAccount();
              router.replace('/profile');
            } catch (e) {
              Alert.alert(
                'Could not delete account',
                e instanceof Error ? e.message : 'Something went wrong. Try again.',
              );
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <Pressable
          style={styles.headerBtn}
          onPress={() => (router.canGoBack() ? router.back() : router.replace('/profile'))}
          hitSlop={8}
        >
          <Ionicons name="arrow-back" size={20} color={Palette.text} />
        </Pressable>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={styles.sectionLabel}>PREFERENCES</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="notifications-outline"
            title="Notifications"
            subtitle="Local law/specialty tips and ground-report alerts"
            right={
              notifsReady ? (
                <Switch
                  value={notifsEnabled}
                  onValueChange={toggleNotifications}
                  trackColor={{ false: Palette.border, true: Palette.primarySoft }}
                  thumbColor={notifsEnabled ? Palette.primary : '#FFFFFF'}
                />
              ) : (
                <ActivityIndicator size="small" color={Palette.textMuted} />
              )
            }
          />
          <View style={styles.divider} />
          <SettingsRow
            icon="trash-bin-outline"
            title="Clear cached forecast data"
            subtitle={clearedNotice ? 'Cleared.' : 'Frees up space; next visit re-fetches live data'}
            onPress={clearCache}
            disabled={clearing}
            right={
              clearing ? (
                <ActivityIndicator size="small" color={Palette.textMuted} />
              ) : clearedNotice ? (
                <Ionicons name="checkmark-circle" size={18} color={Palette.primary} />
              ) : (
                <Ionicons name="chevron-forward" size={16} color={Palette.textDim} />
              )
            }
          />
        </View>

        <Text style={styles.sectionLabel}>ACCOUNT</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="create-outline"
            title="Change username"
            subtitle="Tap the pencil next to your name on your profile"
            onPress={() => router.replace('/profile')}
            right={<Ionicons name="chevron-forward" size={16} color={Palette.textDim} />}
          />
        </View>

        <Text style={[styles.sectionLabel, styles.dangerLabel]}>DANGER ZONE</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="trash-outline"
            iconColor={Palette.danger}
            iconBg={Palette.dangerSoft}
            title="Delete account"
            subtitle="Permanently erase your account and everything in it"
            onPress={confirmDeleteAccount}
            disabled={deleting}
            right={
              deleting ? (
                <ActivityIndicator size="small" color={Palette.danger} />
              ) : (
                <Ionicons name="chevron-forward" size={16} color={Palette.danger} />
              )
            }
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Space.lg,
    paddingVertical: Space.md,
  },
  headerBtn: {
    width: 38,
    height: 38,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    ...Type.heading,
    color: Palette.text,
  },
  content: {
    padding: Space.lg,
    paddingBottom: Space.section,
  },
  sectionLabel: {
    ...Type.eyebrow,
    fontSize: 11,
    color: Palette.textMuted,
    marginTop: Space.lg,
    marginBottom: Space.sm,
    marginLeft: Space.xs,
  },
  dangerLabel: {
    color: Palette.danger,
  },
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    paddingHorizontal: Space.lg,
    ...Shadow.soft,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    paddingVertical: Space.md,
  },
  rowDisabled: { opacity: 0.6 },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: { flex: 1 },
  rowTitle: {
    ...Type.label,
    fontSize: 14,
    color: Palette.text,
  },
  rowSubtitle: {
    ...Type.caption,
    fontSize: 11,
    color: Palette.textMuted,
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: Palette.borderSoft,
  },
});
