import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Space, Type } from '../../constants/trip-theme';

function partOfDay(hour: number) {
  if (hour < 12) return { label: 'Good morning', icon: 'sunny-outline' as const };
  if (hour < 17) return { label: 'Good afternoon', icon: 'partly-sunny-outline' as const };
  return { label: 'Good evening', icon: 'moon-outline' as const };
}

export function Greeting({ name = 'Explorer' }: { name?: string }) {
  const period = partOfDay(new Date().getHours());

  return (
    <View style={styles.wrap}>
      <View style={styles.eyebrow}>
        <Ionicons name={period.icon} size={13} color={Palette.accent} />
        <Text style={styles.eyebrowText}>{period.label.toUpperCase()}</Text>
      </View>

      <Text style={styles.name}>
        {name.toUpperCase()}
        <Text style={styles.period}>.</Text>
      </Text>

      <Text style={styles.sub}>
        Kandy is running clear. Your window opens in{' '}
        <Text style={styles.subAccent}>2 hours</Text>.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingBottom: Space.xxl,
  },
  eyebrow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: Space.sm,
  },
  eyebrowText: {
    ...Type.section,
    color: Palette.accent,
  },
  name: {
    ...Type.hero,
    color: Palette.text,
  },
  period: {
    color: Palette.accent,
  },
  sub: {
    ...Type.body,
    color: Palette.textMuted,
    marginTop: Space.sm,
  },
  subAccent: {
    color: Palette.text,
    fontFamily: Type.metric.fontFamily,
    fontSize: 13,
  },
});
