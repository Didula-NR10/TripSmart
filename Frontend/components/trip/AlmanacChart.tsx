import React, { useMemo, useState } from 'react';
import { LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Rect, Circle } from 'react-native-svg';
import { District } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const HEIGHT = 170;
const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

export type MonthStat = { month: number; high: number; low: number; mean: number; rain: number };

export function historicalSeries(district: District): MonthStat[] {
  const lapse = district.elevation / 150;
  const wet = district.zone === 'wet' ? 1 : district.zone === 'dry' ? 0.35 : 0.65;
  return MONTHS.map((_, i) => {
    const seasonal = Math.cos(((i - 3) / 12) * Math.PI * 2);
    const mean = 28 - lapse + seasonal * 1.8;
    const monsoon = Math.max(0, Math.sin(((i - 4) / 12) * Math.PI * 2)) * 1.4 + 0.5;
    return {
      month: i,
      high: Number((mean + 4.4).toFixed(1)),
      low: Number((mean - 4.8).toFixed(1)),
      mean: Number(mean.toFixed(1)),
      rain: Math.round(monsoon * wet * 190),
    };
  });
}

type Props = {
  district: District;
  selected: number;
  todayMean?: number;
};

export function AlmanacChart({ district, selected, todayMean }: Props) {
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);
  const series = useMemo(() => historicalSeries(district), [district]);

  const stats = useMemo(() => {
    if (!width) return null;
    const highs = series.map((s) => s.high);
    const lows = series.map((s) => s.low);
    const max = Math.max(...highs) + 2;
    const min = Math.min(...lows) - 2;
    const span = max - min;

    const slot = width / 12;
    const toY = (t: number) => 12 + (1 - (t - min) / span) * (HEIGHT - 34);

    return { series, slot, toY, max, min };
  }, [series, width]);

  const active = series[selected];

  return (
    <View>
      <View style={styles.plot} onLayout={onLayout}>
        {stats ? (
          <Svg width={width} height={HEIGHT}>
            {stats.series.map((s) => {
              const cx = s.month * stats.slot + stats.slot / 2;
              const on = s.month === selected;
              return (
                <React.Fragment key={s.month}>
                  <Line
                    x1={cx}
                    y1={stats.toY(s.high)}
                    x2={cx}
                    y2={stats.toY(s.low)}
                    stroke={on ? Palette.primary : Palette.border}
                    strokeWidth={on ? 7 : 6}
                    strokeLinecap="round"
                  />
                  <Circle
                    cx={cx}
                    cy={stats.toY(s.mean)}
                    r={2.5}
                    fill={on ? Palette.onDark : Palette.textDim}
                  />
                </React.Fragment>
              );
            })}

            {todayMean !== undefined ? (
              <Line
                x1={0}
                y1={stats.toY(todayMean)}
                x2={width}
                y2={stats.toY(todayMean)}
                stroke={Palette.warn}
                strokeWidth={1.5}
                strokeDasharray="4 4"
              />
            ) : null}
          </Svg>
        ) : null}
      </View>

      <View style={styles.axis}>
        {MONTHS.map((m, i) => (
          <Text key={i} style={[styles.month, i === selected && styles.monthOn]}>
            {m}
          </Text>
        ))}
      </View>

      <View style={styles.readout}>
        <Stat label="10-yr high" value={`${active.high}°`} />
        <Stat label="10-yr mean" value={`${active.mean}°`} />
        <Stat label="10-yr low" value={`${active.low}°`} />
        <Stat label="Rainfall" value={`${active.rain} mm`} tone={Palette.warn} />
      </View>

      {todayMean !== undefined ? (
        <Text style={styles.legend}>
          Dashed line: today&apos;s predicted mean of {todayMean.toFixed(1)}°, plotted against the
          10-year baseline.
        </Text>
      ) : null}
    </View>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={[styles.statValue, tone ? { color: tone } : null]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  plot: {
    height: HEIGHT,
  },
  axis: {
    flexDirection: 'row',
    marginTop: Space.xs,
  },
  month: {
    flex: 1,
    textAlign: 'center',
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
  monthOn: {
    color: Palette.primary,
    fontFamily: Type.label.fontFamily,
  },
  readout: {
    flexDirection: 'row',
    marginTop: Space.lg,
    backgroundColor: Palette.canvas,
    borderRadius: Radius.md,
    paddingVertical: Space.md,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    ...Type.label,
    color: Palette.text,
  },
  statLabel: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    marginTop: 2,
  },
  legend: {
    ...Type.body,
    fontSize: 11,
    color: Palette.textDim,
    marginTop: Space.md,
  },
});
