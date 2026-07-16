import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AdvisoryLevel, Forecast24, Hour24 } from '../../lib/api';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const skin = (level: AdvisoryLevel) =>
  ({
    GOOD: { bg: Palette.primaryTint, fg: Palette.primaryDeep, rule: Palette.primary, icon: 'sunny' as const },
    CAUTION: { bg: Palette.warnSoft, fg: '#7A5A12', rule: Palette.warn, icon: 'alert-circle' as const },
    AVOID: { bg: Palette.dangerSoft, fg: '#7E2A20', rule: Palette.danger, icon: 'umbrella' as const },
  })[level];

function HourBox({ h }: { h: Hour24 }) {
  const s = skin(h.advisoryLevel);
  return (
    <View style={[styles.box, { backgroundColor: s.bg, borderColor: s.rule }]}>
      <Text style={[styles.boxOffset, { color: s.fg }]}>+{h.offset}h</Text>
      <Text style={[styles.boxLabel, { color: s.fg }]}>{h.label}</Text>
      <Ionicons name={s.icon} size={17} color={s.rule} />
      <Text style={[styles.boxTemp, { color: s.fg }]}>{Math.round(h.temp)}°</Text>
      <View style={styles.boxRow}>
        <Ionicons name="water-outline" size={10} color={s.fg} />
        <Text style={[styles.boxMeta, { color: s.fg }]}>{Math.round(h.humidity)}%</Text>
      </View>
      {h.rain > 0.05 ? (
        <View style={styles.boxRow}>
          <Ionicons name="rainy-outline" size={10} color={s.fg} />
          <Text style={[styles.boxMeta, { color: s.fg }]}>{h.rain.toFixed(1)}</Text>
        </View>
      ) : null}
    </View>
  );
}

export function Next24Strip({ forecast }: { forecast: Forecast24 }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.strip}
    >
      {forecast.hours.map((h) => (
        <HourBox key={h.offset} h={h} />
      ))}
    </ScrollView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export function Next24Summary({ forecast }: { forecast: Forecast24 }) {
  const s = forecast.summary;
  const verdictSkin = skin(s.advisoryLevel);
  const ranAt = new Date(forecast.origin);

  return (
    <View style={styles.card}>
      <View style={[styles.verdict, { backgroundColor: verdictSkin.bg }]}>
        <Ionicons
          name={s.advisoryLevel === 'GOOD' ? 'checkmark-circle' : 'warning'}
          size={17}
          color={verdictSkin.rule}
        />
        <Text style={[styles.verdictText, { color: verdictSkin.fg }]}>{s.verdict}</Text>
      </View>

      <View style={styles.stats}>
        <Stat label="Temperature" value={`${s.tempMin.toFixed(1)}–${s.tempMax.toFixed(1)}°`} />
        <Stat label="Average" value={`${s.tempAvg.toFixed(1)}°`} />
        <Stat label="Total rain" value={`${s.totalRain.toFixed(2)} mm`} />
      </View>
      <View style={styles.stats}>
        <Stat label="Humidity" value={`${s.humidityMin.toFixed(0)}–${s.humidityMax.toFixed(0)}%`} />
        <Stat label="Wet hours" value={`${s.wetHours} / 24`} />
        <Stat label="Advisory" value={s.advisoryLevel} />
      </View>

      <View style={styles.originRow}>
        <Ionicons name="hardware-chip-outline" size={12} color={Palette.textDim} />
        <Text style={styles.origin}>
          GRU model run{' '}
          {ranAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · saved to
          Supabase · cached on device for 24 h
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  strip: {
    gap: Space.sm,
    paddingRight: Space.lg,
  },
  box: {
    width: 74,
    paddingVertical: Space.md,
    borderRadius: Radius.lg,
    borderWidth: 1,
    alignItems: 'center',
    gap: 3,
  },
  boxOffset: {
    ...Type.caption,
    fontSize: 9,
    opacity: 0.75,
  },
  boxLabel: {
    ...Type.label,
    fontSize: 11,
  },
  boxTemp: {
    ...Type.title,
    fontSize: 17,
  },
  boxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  boxMeta: {
    ...Type.caption,
    fontSize: 10,
  },
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.lg,
    marginTop: Space.md,
  },
  verdict: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
  },
  verdictText: {
    ...Type.label,
    flex: 1,
  },
  stats: {
    flexDirection: 'row',
    marginTop: Space.lg,
  },
  stat: {
    flex: 1,
  },
  statValue: {
    ...Type.label,
    color: Palette.text,
  },
  statLabel: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
    marginTop: 2,
  },
  originRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: Space.lg,
    paddingTop: Space.md,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  origin: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
    flex: 1,
  },
});
