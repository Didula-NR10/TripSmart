import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { District } from '../../constants/districts';
import { historicalSeries } from './AlmanacChart';
import { Prediction, totalRain } from '../../lib/engine';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

type Props = {
  district: District;
  prediction: Prediction;
  days?: number;
};

export function HybridTimeline({ district, prediction, days = 6 }: Props) {
  const series = historicalSeries(district);
  const today = new Date();

  const rows = Array.from({ length: days }).map((_, i) => {
    const date = new Date(today);
    date.setDate(today.getDate() + i);
    const stat = series[date.getMonth()];
    const live = i === 0;
    const rain = live ? totalRain(prediction) : Math.round((stat.rain / 30) * 10) / 10;
    const risk = !live && stat.rain > 180;
    return {
      key: date.toISOString().slice(0, 10),
      label: date.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' }),
      source: live ? 'GRU prediction' : '10-year baseline',
      rain,
      temp: live ? prediction.hours[12].temp : stat.mean,
      live,
      risk,
    };
  });

  return (
    <View>
      {rows.map((row) => (
        <View key={row.key} style={styles.row}>
          <View style={[styles.rail, row.live ? styles.railLive : styles.railHist]} />
          <View style={styles.body}>
            <View style={styles.head}>
              <Text style={styles.day}>{row.label}</Text>
              <View style={[styles.tag, row.live ? styles.tagLive : styles.tagHist]}>
                <Text style={[styles.tagText, row.live && styles.tagTextLive]}>
                  {row.live ? 'LIVE' : 'HISTORICAL'}
                </Text>
              </View>
            </View>
            <Text style={styles.meta}>
              {Math.round(row.temp)}° · {row.rain} mm · {row.source}
            </Text>
            {row.risk ? (
              <View style={styles.risk}>
                <Ionicons name="warning-outline" size={12} color={Palette.warn} />
                <Text style={styles.riskText}>
                  This week falls inside {district.name}&apos;s historical monsoon band.
                </Text>
              </View>
            ) : null}
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: Space.md,
  },
  rail: {
    width: 3,
    borderRadius: Radius.pill,
    marginBottom: Space.sm,
  },
  railLive: {
    backgroundColor: Palette.primary,
  },
  railHist: {
    backgroundColor: Palette.border,
  },
  body: {
    flex: 1,
    paddingBottom: Space.lg,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
  },
  day: {
    ...Type.label,
    color: Palette.text,
  },
  tag: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: Radius.sm,
  },
  tagLive: {
    backgroundColor: Palette.primarySoft,
  },
  tagHist: {
    backgroundColor: Palette.neutralChip,
  },
  tagText: {
    ...Type.caption,
    fontSize: 8,
    letterSpacing: 0.8,
    color: Palette.textMuted,
  },
  tagTextLive: {
    color: Palette.primaryDeep,
  },
  meta: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 3,
  },
  risk: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: Space.sm,
    backgroundColor: Palette.warnSoft,
    borderRadius: Radius.sm,
    paddingHorizontal: Space.sm,
    paddingVertical: 6,
  },
  riskText: {
    ...Type.caption,
    color: '#7A5A12',
    flex: 1,
  },
});
