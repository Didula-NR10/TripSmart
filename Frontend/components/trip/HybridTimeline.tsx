import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { District } from '../../constants/districts';
import { OutlookDay, fetchWeeklyOutlook } from '../../lib/api';
import { useAuthGate } from '../../lib/auth';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const confidenceSkin = {
  high: { label: 'GRU MODEL · HIGH', bg: Palette.primarySoft, fg: Palette.primaryDeep },
  medium: { label: 'GRU + PATTERN · MEDIUM', bg: Palette.warnSoft, fg: '#7A5A12' },
  low: { label: 'GRU + PATTERN · LOW', bg: Palette.neutralChip, fg: Palette.textMuted },
} as const;

const advisoryColor = {
  GOOD: Palette.primary,
  CAUTION: Palette.warn,
  AVOID: Palette.danger,
} as const;

export function HybridTimeline({ district }: { district: District }) {
  const gate = useAuthGate();
  const [days, setDays] = useState<OutlookDay[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedFor = useRef<string | null>(null);

  // A new district invalidates the previous outlook.
  useEffect(() => {
    if (loadedFor.current && loadedFor.current !== district.key) {
      setDays(null);
      setError(null);
      loadedFor.current = null;
    }
  }, [district.key]);

  const run = async () => {
    if (!gate()) return; // week-ahead predictions need an account
    setLoading(true);
    setError(null);
    try {
      const result = await fetchWeeklyOutlook(district.key);
      setDays(result);
      loadedFor.current = district.key;
    } catch {
      setError('Could not reach the forecast model. Check the backend is running and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View>
      {!days ? (
        <Pressable style={[styles.cta, loading && styles.ctaBusy]} onPress={run} disabled={loading}>
          {loading ? (
            <ActivityIndicator size="small" color={Palette.onDark} />
          ) : (
            <Ionicons name="analytics-outline" size={16} color={Palette.onDark} />
          )}
          <Text style={styles.ctaText}>
            {loading ? `Running the model day by day…` : `Analyse the week in ${district.name}`}
          </Text>
        </Pressable>
      ) : null}

      {error ? (
        <View style={styles.error}>
          <Ionicons name="cloud-offline-outline" size={14} color={Palette.danger} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {days
        ? days.map((day, i) => {
            const skin = confidenceSkin[day.confidence];
            const live = day.confidence === 'high';
            return (
              <View key={day.date} style={styles.row}>
                <View style={[styles.rail, live ? styles.railLive : styles.railHist]} />
                <View style={[styles.body, i === days.length - 1 && { paddingBottom: 0 }]}>
                  <View style={styles.head}>
                    <Text style={styles.day}>
                      {day.weekday} {parseInt(day.date.slice(8, 10), 10)}
                    </Text>
                    <View style={[styles.tag, { backgroundColor: skin.bg }]}>
                      <Text style={[styles.tagText, { color: skin.fg }]}>{skin.label}</Text>
                    </View>
                  </View>
                  <Text style={styles.meta}>
                    {Math.round(day.tempMin)}–{Math.round(day.tempMax)}° · {day.totalRain} mm
                    {day.wetHours > 0 ? ` · ${day.wetHours} wet h` : ''}
                  </Text>
                  <Text style={[styles.verdict, { color: advisoryColor[day.advisoryLevel] }]}>
                    {day.verdict}
                  </Text>
                </View>
              </View>
            );
          })
        : null}

      {days ? (
        <Pressable style={styles.refresh} onPress={run} disabled={loading}>
          {loading ? (
            <ActivityIndicator size="small" color={Palette.primary} />
          ) : (
            <Ionicons name="refresh-outline" size={13} color={Palette.primary} />
          )}
          <Text style={styles.refreshText}>
            {loading ? 'Re-running…' : 'Re-run the outlook'}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    backgroundColor: Palette.primaryDeep,
    borderRadius: Radius.md,
    paddingVertical: Space.md,
  },
  ctaBusy: {
    opacity: 0.75,
  },
  ctaText: {
    ...Type.label,
    color: Palette.onDark,
  },
  error: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: Space.md,
    padding: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.dangerSoft,
  },
  errorText: {
    ...Type.caption,
    color: '#7E2A20',
    flex: 1,
    lineHeight: 15,
  },
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
  tagText: {
    ...Type.caption,
    fontSize: 8,
    letterSpacing: 0.8,
  },
  meta: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 3,
  },
  verdict: {
    ...Type.caption,
    fontSize: 10,
    marginTop: 2,
  },
  refresh: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    marginTop: Space.md,
    paddingVertical: Space.sm,
  },
  refreshText: {
    ...Type.label,
    fontSize: 11,
    color: Palette.primary,
  },
});
