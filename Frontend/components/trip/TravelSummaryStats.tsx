import { StyleSheet, Text, View } from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export type SummaryStat = {
  iconLib: 'ion' | 'mci';
  icon: string;
  value: string;
  label: string;
};

export function TravelSummaryStats({ stats }: { stats: SummaryStat[] }) {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Your travel summary</Text>
      <View style={styles.row}>
        {stats.map((s, i) => (
          <View key={s.label} style={styles.col}>
            {i > 0 ? <View style={styles.sep} /> : null}
            <View style={styles.iconWrap}>
              {s.iconLib === 'mci' ? (
                <MaterialCommunityIcons name={s.icon as any} size={16} color={Palette.onDark} />
              ) : (
                <Ionicons name={s.icon as any} size={16} color={Palette.onDark} />
              )}
            </View>
            <Text style={styles.value}>{s.value}</Text>
            <Text style={styles.label}>{s.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.primaryDeep,
    borderRadius: Radius.xl,
    padding: Space.lg,
  },
  title: {
    ...Type.label,
    fontSize: 15,
    color: Palette.onDark,
    marginBottom: Space.lg,
  },
  row: {
    flexDirection: 'row',
  },
  col: {
    flex: 1,
    alignItems: 'center',
  },
  sep: {
    position: 'absolute',
    left: 0,
    top: 6,
    bottom: 6,
    borderLeftWidth: 1,
    borderLeftColor: 'rgba(255, 255, 255, 0.24)',
    borderStyle: 'dashed',
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(255, 255, 255, 0.16)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.sm,
  },
  value: {
    fontFamily: Type.title.fontFamily,
    fontSize: 19,
    color: Palette.onDark,
  },
  label: {
    ...Type.caption,
    fontSize: 9.5,
    color: Palette.onDarkMuted,
    marginTop: 2,
    textAlign: 'center',
  },
});
