import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop, Circle, Line } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import { hourly, windowRange, HourPoint } from '../../constants/trip-data';
import { Palette, Space, Type } from '../../constants/trip-theme';

const HEIGHT = 78;
const PAD_TOP = 8;
const PAD_BOTTOM = 10;

const skyIcon: Record<HourPoint['sky'], keyof typeof Ionicons.glyphMap> = {
  clear: 'sunny-outline',
  partly: 'partly-sunny-outline',
  cloud: 'cloud-outline',
  rain: 'rainy-outline',
  night: 'moon-outline',
};

function buildPath(points: { x: number; y: number }[]) {
  if (points.length < 2) return '';
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const current = points[i];
    const next = points[i + 1];
    const midX = (current.x + next.x) / 2;
    d += ` C ${midX} ${current.y}, ${midX} ${next.y}, ${next.x} ${next.y}`;
  }
  return d;
}

export function ForecastChart({ width }: { width: number }) {
  const geometry = useMemo(() => {
    const temps = hourly.map((h) => h.temp);
    const min = Math.min(...temps) - 1.5;
    const max = Math.max(...temps) + 1.5;
    const span = max - min;

    const toX = (hour: number) => (hour / 24) * width;
    const toY = (temp: number) =>
      PAD_TOP + (1 - (temp - min) / span) * (HEIGHT - PAD_TOP - PAD_BOTTOM);

    const points = hourly.map((h) => ({ x: toX(h.hour), y: toY(h.temp) }));
    const line = buildPath(points);
    const area = `${line} L ${points[points.length - 1].x} ${HEIGHT} L ${points[0].x} ${HEIGHT} Z`;

    const bandX = toX(windowRange.from);
    const bandWidth = toX(windowRange.to) - bandX;

    const peak = hourly.reduce((best, h) =>
      h.hour >= windowRange.from && h.hour <= windowRange.to && h.temp > best.temp ? h : best,
      hourly[0],
    );

    return {
      line,
      area,
      bandX,
      bandWidth,
      marker: { x: toX(peak.hour), y: toY(peak.temp) },
      axis: [max, (max + min) / 2, min].map((t) => Math.round(t)),
    };
  }, [width]);

  return (
    <View>
      <View style={styles.iconRow}>
        {hourly.map((h) => (
          <Ionicons
            key={h.hour}
            name={skyIcon[h.sky]}
            size={13}
            color={
              h.hour >= windowRange.from && h.hour <= windowRange.to
                ? Palette.accent
                : Palette.textDim
            }
          />
        ))}
      </View>

      <View style={styles.plot}>
        <View style={styles.axis}>
          {geometry.axis.map((value) => (
            <Text key={value} style={styles.axisText}>
              {value}°
            </Text>
          ))}
        </View>

        <Svg width={width} height={HEIGHT}>
          <Defs>
            <LinearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={Palette.cyan} stopOpacity="0.22" />
              <Stop offset="1" stopColor={Palette.cyan} stopOpacity="0" />
            </LinearGradient>
          </Defs>

          <Rect
            x={geometry.bandX}
            y={PAD_TOP}
            width={geometry.bandWidth}
            height={HEIGHT - PAD_TOP}
            fill={Palette.accentGlow}
            rx={4}
          />
          <Line
            x1={geometry.bandX}
            y1={PAD_TOP}
            x2={geometry.bandX}
            y2={HEIGHT}
            stroke={Palette.accentEdge}
            strokeWidth={1}
          />
          <Line
            x1={geometry.bandX + geometry.bandWidth}
            y1={PAD_TOP}
            x2={geometry.bandX + geometry.bandWidth}
            y2={HEIGHT}
            stroke={Palette.accentEdge}
            strokeWidth={1}
          />

          <Path d={geometry.area} fill="url(#fill)" />
          <Path
            d={geometry.line}
            stroke={Palette.cyan}
            strokeWidth={1.75}
            fill="none"
            strokeLinecap="round"
          />
          <Circle
            cx={geometry.marker.x}
            cy={geometry.marker.y}
            r={3.5}
            fill={Palette.accent}
            stroke={Palette.surfaceInset}
            strokeWidth={2}
          />
        </Svg>
      </View>

      <View style={styles.ticks}>
        {['12 AM', '4 AM', '8 AM', '12 PM', '4 PM', '8 PM'].map((tick) => (
          <Text key={tick} style={styles.tickText}>
            {tick}
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  iconRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 2,
    marginBottom: Space.sm,
  },
  plot: {
    position: 'relative',
  },
  axis: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 10,
    justifyContent: 'space-between',
    zIndex: 2,
  },
  axisText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 9,
    color: Palette.textDim,
    backgroundColor: Palette.surfaceInset,
    paddingRight: 3,
  },
  ticks: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: Space.xs,
  },
  tickText: {
    fontFamily: Type.metric.fontFamily,
    fontSize: 9,
    color: Palette.textDim,
    letterSpacing: 0.3,
  },
});
