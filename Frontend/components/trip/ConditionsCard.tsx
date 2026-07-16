import { useState } from 'react';
import { LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Card } from './Card';
import { ForecastChart } from './ForecastChart';
import { bestWindow, currentConditions } from '../../constants/trip-data';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, tone ? { color: tone } : null]}>{value}</Text>
    </View>
  );
}

export function ConditionsCard() {
  const [chartWidth, setChartWidth] = useState(0);

  const onLayout = (event: LayoutChangeEvent) => {
    setChartWidth(event.nativeEvent.layout.width);
  };

  return (
    <Card style={styles.card}>
      <LinearGradient
        colors={['#16342C', '#0F2029', Palette.surface]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.hero}
      >
        <View style={styles.heroTop}>
          <View style={styles.pin}>
            <Ionicons name="location-outline" size={12} color={Palette.accent} />
            <Text style={styles.pinText}>CURRENT LOCATION</Text>
          </View>
          <View style={styles.live}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
        </View>

        <View style={styles.heroBody}>
          <View style={styles.heroLeft}>
            <Text style={styles.district}>{currentConditions.district}</Text>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{currentConditions.summary.toUpperCase()}</Text>
            </View>
          </View>

          <View style={styles.heroRight}>
            <View style={styles.tempRow}>
              <Ionicons name="sunny" size={20} color={Palette.warn} />
              <Text style={styles.temp}>{currentConditions.temp}°C</Text>
            </View>
            <Text style={styles.feels}>Feels like {currentConditions.feelsLike}°C</Text>
          </View>
        </View>
      </LinearGradient>

      <View style={styles.body}>
        <Pressable style={styles.window}>
          <View style={styles.windowGo}>
            <Text style={styles.windowGoText}>GO</Text>
          </View>
          <View style={styles.windowCopy}>
            <Text style={styles.windowLabel}>BEST TRAVEL WINDOW</Text>
            <Text style={styles.windowValue}>
              {bestWindow.start} — {bestWindow.end}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={Palette.base} />
        </Pressable>

        <View style={styles.chart} onLayout={onLayout}>
          {chartWidth > 0 ? <ForecastChart width={chartWidth} /> : null}
        </View>

        <View style={styles.divider} />

        <View style={styles.metrics}>
          <Metric label="TEMP" value={`${currentConditions.temp}°C`} />
          <View style={styles.metricRule} />
          <Metric label="RAIN" value={`${currentConditions.rain} mm`} tone={Palette.accent} />
          <View style={styles.metricRule} />
          <Metric label="HUMIDITY" value={`${currentConditions.humidity}%`} tone={Palette.cyan} />
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    overflow: 'hidden',
    padding: 0,
  },
  hero: {
    padding: Space.lg,
    paddingBottom: Space.xl,
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Space.lg,
  },
  pin: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  pinText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 9,
    letterSpacing: 1.2,
    color: Palette.textMuted,
  },
  live: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: Radius.pill,
    backgroundColor: Palette.accentGlow,
  },
  liveDot: {
    width: 5,
    height: 5,
    borderRadius: Radius.pill,
    backgroundColor: Palette.accent,
  },
  liveText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 8,
    letterSpacing: 1,
    color: Palette.accent,
  },
  heroBody: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },
  heroLeft: {
    alignItems: 'flex-start',
    gap: Space.sm,
  },
  district: {
    ...Type.title,
    color: Palette.text,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Palette.borderSoft,
    backgroundColor: 'rgba(10, 15, 23, 0.45)',
  },
  badgeText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 9,
    letterSpacing: 1,
    color: Palette.textMuted,
  },
  heroRight: {
    alignItems: 'flex-end',
  },
  tempRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  temp: {
    ...Type.metricLarge,
    color: Palette.text,
  },
  feels: {
    ...Type.caption,
    color: Palette.textMuted,
    marginTop: 2,
  },
  body: {
    padding: Space.lg,
    paddingTop: Space.md,
  },
  window: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    backgroundColor: Palette.accent,
    borderRadius: Radius.md,
    padding: Space.md,
    marginBottom: Space.lg,
  },
  windowGo: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.sm,
    backgroundColor: 'rgba(10, 15, 23, 0.28)',
  },
  windowGoText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 10,
    letterSpacing: 1,
    color: Palette.base,
  },
  windowCopy: {
    flex: 1,
  },
  windowLabel: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 8,
    letterSpacing: 1.2,
    color: 'rgba(10, 15, 23, 0.7)',
  },
  windowValue: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 13,
    color: Palette.base,
    marginTop: 1,
  },
  chart: {
    backgroundColor: Palette.surfaceInset,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
  },
  divider: {
    height: 1,
    backgroundColor: Palette.border,
    marginVertical: Space.lg,
  },
  metrics: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  metric: {
    flex: 1,
    gap: 3,
  },
  metricLabel: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 9,
    letterSpacing: 1.1,
    color: Palette.textDim,
  },
  metricValue: {
    ...Type.metric,
    color: Palette.text,
  },
  metricRule: {
    width: 1,
    height: 26,
    backgroundColor: Palette.border,
    marginHorizontal: Space.md,
  },
});
