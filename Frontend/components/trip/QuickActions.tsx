/**
 * QuickActions — the 2x2 grid at the bottom of the Profile tab. Each tile
 * routes to the closest real screen the app already has; "Help center" has
 * no dedicated screen yet, so it surfaces a short in-app notice instead of a
 * dead tap.
 */
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

type Action = {
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  detail: string;
  onPress: () => void;
};

export function QuickActions() {
  const router = useRouter();

  const actions: Action[] = [
    {
      key: 'offline',
      icon: 'cloud-download-outline',
      title: 'Offline maps',
      detail: 'Download for offline access',
      onPress: () => router.push('/trips'),
    },
    {
      key: 'saved',
      icon: 'heart-outline',
      title: 'Saved places',
      detail: 'Your favorite destinations',
      onPress: () => router.push('/saved'),
    },
    {
      key: 'contribute',
      icon: 'cloud-upload-outline',
      title: 'Contribute',
      detail: 'Share reports and help others',
      onPress: () => router.push('/reports'),
    },
    {
      key: 'help',
      icon: 'help-circle-outline',
      title: 'Help center',
      detail: 'Get support and find answers',
      onPress: () =>
        Alert.alert(
          'Help center',
          'Support articles are coming soon. For now, post a ground report if something looks wrong.',
        ),
    },
  ];

  return (
    <View style={styles.grid}>
      {actions.map((a) => (
        <Pressable key={a.key} style={styles.tile} onPress={a.onPress}>
          <View style={styles.iconWrap}>
            <Ionicons name={a.icon} size={17} color={Palette.primary} />
          </View>
          <Text style={styles.title}>{a.title}</Text>
          <Text style={styles.detail}>{a.detail}</Text>
        </Pressable>
      ))}
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
    backgroundColor: Palette.surface,
    borderRadius: Radius.lg,
    padding: Space.lg,
    ...Shadow.soft,
  },
  iconWrap: {
    width: 34,
    height: 34,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.sm,
  },
  title: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
  },
  detail: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
    marginTop: 2,
  },
});
