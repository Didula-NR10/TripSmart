import { Pressable, StyleSheet, Text, View } from 'react-native';
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
      key: 'forecast',
      icon: 'sunny-outline',
      title: 'Weather Forecast',
      detail: '24-hour outlook by district',
      onPress: () => router.push('/'),
    },
    {
      key: 'guide',
      icon: 'business-outline',
      title: 'Local Guide',
      detail: 'Laws, etiquette & safety tips',
      onPress: () => router.push('/explore'),
    },
    {
      key: 'route',
      icon: 'navigate-outline',
      title: 'Route Intelligence',
      detail: 'Compare destinations & smart routing',
      onPress: () => router.push('/plan'),
    },
    {
      key: 'reports',
      icon: 'chatbubbles-outline',
      title: 'Ground Reports',
      detail: 'Real conditions from real travellers',
      onPress: () => router.push('/reports'),
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
