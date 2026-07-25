/**
 * ProfileHero — the Profile tab's full-bleed photo header: a sunrise hiking
 * shot fades into the canvas from the left (same technique as PageHero) so
 * the "Profile" title sits on a clean surface while the photo stays visible
 * on the right. Settings and notifications sit top-right as circular buttons.
 */
import { useEffect, useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getNotificationHistory, subscribeNotificationHistory } from '../../lib/notify';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

const HERO_IMAGE =
  'https://upload.wikimedia.org/wikipedia/commons/2/29/Hikers_watching_sunrise_at_Mount_Pulag_summit.jpg';

export function ProfileHero({
  title,
  subtitle,
  onPressNotifications,
}: {
  title: string;
  subtitle: string;
  onPressNotifications: () => void;
}) {
  const insets = useSafeAreaInsets();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    getNotificationHistory().then((entries) => setUnread(entries.filter((e) => !e.read).length));
    return subscribeNotificationHistory((entries) =>
      setUnread(entries.filter((e) => !e.read).length),
    );
  }, []);

  return (
    <View style={styles.wrap}>
      <Image source={{ uri: HERO_IMAGE }} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <LinearGradient
        colors={[Palette.canvas, Palette.canvas, 'rgba(245, 248, 249, 0.55)', 'transparent']}
        locations={[0, 0.36, 0.58, 1]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={StyleSheet.absoluteFill}
      />
      <LinearGradient
        colors={['transparent', 'rgba(245, 248, 249, 0.7)', Palette.canvas]}
        locations={[0.55, 0.84, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={[styles.topRow, { paddingTop: insets.top + Space.sm }]}>
        <Pressable
          style={styles.iconButton}
          onPress={() => Alert.alert('Settings', 'Account and app settings are coming soon.')}
          accessibilityLabel="Settings"
          hitSlop={6}
        >
          <Ionicons name="settings-outline" size={18} color={Palette.text} />
        </Pressable>
        <Pressable
          style={styles.iconButton}
          onPress={onPressNotifications}
          accessibilityLabel="Notifications"
          hitSlop={6}
        >
          <Ionicons name="notifications-outline" size={18} color={Palette.text} />
          {unread > 0 ? <View style={styles.dot} /> : null}
        </Pressable>
      </View>

      <View style={styles.content}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.subtitle}>{subtitle}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 250,
    marginTop: -Space.lg,
    marginHorizontal: -Space.lg,
    marginBottom: Space.xl,
    backgroundColor: Palette.canvas,
    overflow: 'hidden',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: Space.sm,
    paddingHorizontal: Space.lg,
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadow.soft,
  },
  dot: {
    position: 'absolute',
    top: 7,
    right: 8,
    width: 9,
    height: 9,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primary,
    borderWidth: 1.5,
    borderColor: Palette.surface,
  },
  content: {
    flex: 1,
    justifyContent: 'flex-end',
    paddingHorizontal: Space.lg,
    paddingBottom: Space.xl,
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
    maxWidth: '72%',
  },
});
