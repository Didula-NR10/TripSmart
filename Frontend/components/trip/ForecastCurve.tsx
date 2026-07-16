import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { HourPrediction } from '../../lib/engine';
import { Palette, Space, Type } from '../../constants/trip-theme';

const HEIGHT = 96;

type Props = {
  hours: HourPrediction[];
  width: number;
  window?: { from: number; to: number } | null;
  color?: string;
};

export function ForecastCurve({ hours, width, window, color = Palette.primary }: Props) {
  const geo = useMemo(() => {
    const temps = hours.map((h) => h.temp);
    const min = Math.min(...temps) - 1.5;
    const max = Math.max(...temps) + 1.5;
    const span = max - min || 1;

    const toX = (h: number) => (h / 23) * width;
    const toY = (t: number) => 10 + (1 - (t - min) / span) * (HEIGHT - 26);

    const points = hours.map((h) => ({ x: toX(h.hour), y: toY(h.temp) }));
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const mid = (points[i].x + points[i + 1].x) / 2;
      d += ` C ${mid} ${points[i].y}, ${mid} ${points[i + 1].y}, ${points[i + 1].x} ${points[i + 1].y}`;
    }
    const area = `${d} L ${width} ${HEIGHT} L 0 ${HEIGHT} Z`;

    return {
      line: d,
      area,
      bandX: window ? toX(window.from) : 0,
      bandW: window ? toX(window.to) - toX(window.from) : 0,
      hi: Math.round(max - 1.5),
      lo: Math.round(min + 1.5),
    };
  }, [hours, width, window]);

  return (
    <View>
      <Svg width={width} height={HEIGHT}>
        <Defs>
          <LinearGradient id="curveFill" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={color} stopOpacity="0.18" />
            <Stop offset="1" stopColor={color} stopOpacity="0" />
          </LinearGradient>
        </Defs>

        {window ? (
          <Rect
            x={geo.bandX}
            y={0}
            width={geo.bandW}
            height={HEIGHT}
            fill={Palette.primarySoft}
            rx={6}
          />
        ) : null}

        <Path d={geo.area} fill="url(#curveFill)" />
        <Path d={geo.line} stroke={color} strokeWidth={2} fill="none" strokeLinecap="round" />
      </Svg>

      <View style={styles.ticks}>
        {['00', '06', '12', '18', '23'].map((t) => (
          <Text key={t} style={styles.tick}>
            {t}:00
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  ticks: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: Space.xs,
  },
  tick: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
});
