import { useState } from 'react';
import {
  ActivityIndicator,
  LayoutChangeEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ForecastCurve } from './ForecastCurve';
import { DistrictSheet } from './DistrictSheet';
import { districtByKey } from '../../constants/districts';
import { ProfileKey } from '../../constants/profiles';
import { gradeDay } from '../../lib/engine';
import {
  CurrentConditions,
  ForecastBundle,
  cacheForecast,
  fetchCurrentConditions,
  fetchForecastBundle,
} from '../../lib/api';
import { useAuthGate } from '../../lib/auth';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

type Mode = 'now' | 'day';

type Result =
  | { kind: 'now'; a: CurrentConditions; b: CurrentConditions }
  | { kind: 'day'; a: ForecastBundle; b: ForecastBundle };

const compass = (deg: number) =>
  ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(deg / 45) % 8];

export function Comparer({ profileKey }: { profileKey: ProfileKey }) {
  const gate = useAuthGate();
  const [left, setLeft] = useState('nuwaraeliya');
  const [right, setRight] = useState('anuradhapura');
  const [picking, setPicking] = useState<'left' | 'right' | null>(null);
  const [mode, setMode] = useState<Mode>('now');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [width, setWidth] = useState(0);

  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  const pick = (key: string) => {
    if (picking === 'left') setLeft(key);
    else setRight(key);
    setResult(null); // a new pair needs a new comparison
    setError(null);
  };

  const switchMode = (m: Mode) => {
    if (m === mode) return;
    setMode(m);
    setResult(null);
    setError(null);
  };

  const compare = async () => {
    if (!gate()) return; // comparisons need an account
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      if (mode === 'now') {
        const [a, b] = await Promise.all([
          fetchCurrentConditions(left),
          fetchCurrentConditions(right),
        ]);
        setResult({ kind: 'now', a, b });
      } else {
        // Same pipeline as the Forecast tab: 7 days of observations up to this
        // minute feed the GRU, which predicts the next 24 hours. Sequential on
        // purpose — parallel runs contend for the model on the server.
        const a = await fetchForecastBundle(left, { refresh: true });
        const b = await fetchForecastBundle(right, { refresh: true });
        cacheForecast(left, a);
        cacheForecast(right, b);
        setResult({ kind: 'day', a, b });
      }
    } catch {
      setError(
        mode === 'now'
          ? 'Could not reach the weather service. Check the backend is running and try again.'
          : 'Could not reach the forecast model. Check the backend is running and try again.',
      );
    } finally {
      setLoading(false);
    }
  };

  const leftName = districtByKey(left)?.name ?? left;
  const rightName = districtByKey(right)?.name ?? right;

  return (
    <View>
      {/* ── pick the two districts ─────────────────────────────────────── */}
      <View style={styles.picker}>
        <Pressable style={styles.slot} onPress={() => setPicking('left')}>
          <Text style={styles.slotEyebrow}>DESTINATION 1</Text>
          <View style={styles.slotRow}>
            <Ionicons name="location" size={14} color={Palette.primary} />
            <Text style={styles.slotLabel} numberOfLines={1}>
              {leftName}
            </Text>
            <Ionicons name="chevron-down" size={13} color={Palette.textMuted} />
          </View>
        </Pressable>
        <View style={styles.vsBadge}>
          <Text style={styles.vs}>VS</Text>
        </View>
        <Pressable style={styles.slot} onPress={() => setPicking('right')}>
          <Text style={styles.slotEyebrow}>DESTINATION 2</Text>
          <View style={styles.slotRow}>
            <Ionicons name="location" size={14} color={Palette.primary} />
            <Text style={styles.slotLabel} numberOfLines={1}>
              {rightName}
            </Text>
            <Ionicons name="chevron-down" size={13} color={Palette.textMuted} />
          </View>
        </Pressable>
      </View>

      {/* ── choose what to compare ─────────────────────────────────────── */}
      <View style={styles.modes}>
        <Pressable
          style={[styles.mode, mode === 'now' && styles.modeOn]}
          onPress={() => switchMode('now')}
        >
          <Ionicons
            name="rainy-outline"
            size={18}
            color={mode === 'now' ? Palette.onDark : Palette.text}
          />
          <Text style={[styles.modeTitle, mode === 'now' && styles.modeTextOn]}>
            Current conditions
          </Text>
          <Text style={[styles.modeCaption, mode === 'now' && styles.modeCaptionOn]}>
            Live observations from Open-Meteo
          </Text>
        </Pressable>
        <Pressable
          style={[styles.mode, mode === 'day' && styles.modeOn]}
          onPress={() => switchMode('day')}
        >
          <Ionicons
            name="trending-up-outline"
            size={18}
            color={mode === 'day' ? Palette.onDark : Palette.text}
          />
          <Text style={[styles.modeTitle, mode === 'day' && styles.modeTextOn]}>
            Next 24h forecast
          </Text>
          <Text style={[styles.modeCaption, mode === 'day' && styles.modeCaptionOn]}>
            See how the weather is evolving
          </Text>
        </Pressable>
      </View>

      <View style={styles.modeHintRow}>
        <Ionicons name="information-circle-outline" size={14} color={Palette.textDim} />
        <Text style={styles.modeHint}>
          {mode === 'now'
            ? 'Live observations from Open-Meteo — for deciding where to go right now.'
            : 'GRU model run for each district: the last 7 days of weather feed the model, which predicts the next 24 hours.'}
        </Text>
      </View>

      <Pressable
        style={[styles.cta, loading && styles.ctaBusy]}
        onPress={compare}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator size="small" color={Palette.onDark} />
        ) : (
          <Ionicons name="swap-horizontal-outline" size={18} color={Palette.onDark} />
        )}
        <Text style={styles.ctaText}>
          {loading
            ? mode === 'now'
              ? 'Fetching live conditions…'
              : 'Running the model for both…'
            : 'Compare districts'}
        </Text>
      </Pressable>

      {error ? (
        <View style={styles.error}>
          <Ionicons name="cloud-offline-outline" size={14} color={Palette.danger} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {/* ── results ────────────────────────────────────────────────────── */}
      {result?.kind === 'now' ? (
        <NowComparison a={result.a} b={result.b} leftName={leftName} rightName={rightName} />
      ) : null}

      {result?.kind === 'day' ? (
        <View style={styles.results}>
          <View style={styles.chart} onLayout={onLayout}>
            {width > 0 ? (
              <>
                <ForecastCurve
                  hours={result.a.prediction.hours}
                  width={width}
                  color={Palette.primary}
                />
                <View style={styles.overlay}>
                  <ForecastCurve
                    hours={result.b.prediction.hours}
                    width={width}
                    color={Palette.warn}
                  />
                </View>
              </>
            ) : null}
          </View>
          <DayRows
            a={result.a}
            b={result.b}
            leftName={leftName}
            rightName={rightName}
            profileKey={profileKey}
          />
        </View>
      ) : null}

      <DistrictSheet
        visible={picking !== null}
        onClose={() => setPicking(null)}
        onSelect={pick}
        title={picking === 'left' ? 'First destination' : 'Second destination'}
      />
    </View>
  );
}

/* ── current-conditions comparison table ──────────────────────────────── */

function NowComparison({
  a,
  b,
  leftName,
  rightName,
}: {
  a: CurrentConditions;
  b: CurrentConditions;
  leftName: string;
  rightName: string;
}) {
  const rows: { label: string; va: string; vb: string }[] = [
    { label: 'Sky', va: a.condition, vb: b.condition },
    { label: 'Temperature', va: `${a.temp}°C`, vb: `${b.temp}°C` },
    { label: 'Feels like', va: `${a.feelsLike}°C`, vb: `${b.feelsLike}°C` },
    { label: 'Humidity', va: `${a.humidity}%`, vb: `${b.humidity}%` },
    { label: 'Rain (last hour)', va: `${a.rain} mm`, vb: `${b.rain} mm` },
    { label: 'Cloud cover', va: `${a.cloudCover}%`, vb: `${b.cloudCover}%` },
    {
      label: 'Wind',
      va: `${a.windSpeed} km/h ${compass(a.windDirection)}`,
      vb: `${b.windSpeed} km/h ${compass(b.windDirection)}`,
    },
    { label: 'Gusts', va: `${a.windGusts} km/h`, vb: `${b.windGusts} km/h` },
    { label: 'UV index', va: `${a.uvIndex}`, vb: `${b.uvIndex}` },
    { label: 'Pressure', va: `${a.pressure} hPa`, vb: `${b.pressure} hPa` },
  ];

  return (
    <View style={styles.results}>
      <View style={styles.tableHead}>
        <Text style={styles.tableLabel} />
        <Text style={[styles.tableCol, { color: Palette.primaryDeep }]} numberOfLines={1}>
          {leftName}
        </Text>
        <Text style={[styles.tableCol, { color: '#7A5A12' }]} numberOfLines={1}>
          {rightName}
        </Text>
      </View>

      {rows.map((r, i) => (
        <View key={r.label} style={[styles.tableRow, i % 2 === 0 && styles.tableRowAlt]}>
          <Text style={styles.tableLabel}>{r.label}</Text>
          <Text style={styles.tableCol}>{r.va}</Text>
          <Text style={styles.tableCol}>{r.vb}</Text>
        </View>
      ))}

      <View style={styles.footnote}>
        <Ionicons name="time-outline" size={12} color={Palette.textDim} />
        <Text style={styles.footnoteText}>
          Observed {a.observedAt.replace('T', ' ')} · live Open-Meteo data, no model involved.
        </Text>
      </View>
    </View>
  );
}

/* ── next-24h grade rows ──────────────────────────────────────────────── */

function DayRows({
  a,
  b,
  leftName,
  rightName,
  profileKey,
}: {
  a: ForecastBundle;
  b: ForecastBundle;
  leftName: string;
  rightName: string;
  profileKey: ProfileKey;
}) {
  const ga = gradeDay(a.prediction, profileKey);
  const gb = gradeDay(b.prediction, profileKey);
  const winner = ga.score >= gb.score ? 'left' : 'right';

  return (
    <>
      <View style={styles.rows}>
        <Row
          name={leftName}
          color={Palette.primary}
          grade={ga.letter}
          score={ga.score}
          bundle={a}
          win={winner === 'left'}
        />
        <Row
          name={rightName}
          color={Palette.warn}
          grade={gb.letter}
          score={gb.score}
          bundle={b}
          win={winner === 'right'}
        />
      </View>
      <View style={styles.footnote}>
        <Ionicons name="hardware-chip-outline" size={12} color={Palette.textDim} />
        <Text style={styles.footnoteText}>
          Both curves are fresh GRU runs anchored at the moment you pressed compare.
        </Text>
      </View>
    </>
  );
}

function Row({
  name,
  color,
  grade,
  score,
  bundle,
  win,
}: {
  name: string;
  color: string;
  grade: string;
  score: number;
  bundle: ForecastBundle;
  win: boolean;
}) {
  const s = bundle.live.summary;
  return (
    <View style={[styles.row, win && styles.rowWin]}>
      <View style={[styles.swatch, { backgroundColor: color }]} />
      <View style={styles.rowBody}>
        <Text style={styles.rowName}>{name}</Text>
        <Text style={styles.rowMeta}>
          {s.totalRain} mm rain · {s.tempMin}–{s.tempMax}°C · {s.wetHours} wet h · {score}/100
        </Text>
        <Text style={styles.rowVerdict} numberOfLines={2}>
          {s.verdict}
        </Text>
      </View>
      <Text style={[styles.rowGrade, win && styles.rowGradeWin]}>{grade}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  picker: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginBottom: Space.md,
  },
  slot: {
    flex: 1,
    backgroundColor: Palette.surface,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
    ...Shadow.soft,
  },
  slotEyebrow: {
    ...Type.eyebrow,
    fontSize: 9,
    color: Palette.textDim,
  },
  slotRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
  },
  slotLabel: {
    ...Type.label,
    fontSize: 12,
    letterSpacing: -0.2,
    color: Palette.text,
    flex: 1,
  },
  vsBadge: {
    width: 32,
    height: 32,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  vs: {
    ...Type.label,
    fontSize: 11,
    color: Palette.primaryDeep,
  },
  modes: {
    flexDirection: 'row',
    gap: Space.sm,
  },
  mode: {
    flex: 1,
    paddingVertical: Space.md,
    paddingHorizontal: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryTint,
  },
  modeOn: {
    backgroundColor: Palette.primaryDeep,
  },
  modeTitle: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
    marginTop: Space.sm,
  },
  modeCaption: {
    ...Type.caption,
    fontSize: 10,
    lineHeight: 13,
    color: Palette.textMuted,
    marginTop: 2,
  },
  modeTextOn: {
    color: Palette.onDark,
  },
  modeCaptionOn: {
    color: Palette.onDarkMuted,
  },
  modeHintRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: Space.md,
  },
  modeHint: {
    ...Type.caption,
    fontSize: 11,
    color: Palette.textDim,
    lineHeight: 15,
    flex: 1,
  },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    marginTop: Space.md,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryDeep,
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
  results: {
    marginTop: Space.lg,
  },
  chart: {
    position: 'relative',
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  tableHead: {
    flexDirection: 'row',
    paddingVertical: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Palette.border,
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: Space.sm,
    paddingHorizontal: 2,
  },
  tableRowAlt: {
    backgroundColor: Palette.canvas,
    borderRadius: Radius.sm,
  },
  tableLabel: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
    flex: 1.1,
  },
  tableCol: {
    ...Type.label,
    fontSize: 11,
    color: Palette.text,
    flex: 1,
    textAlign: 'right',
  },
  rows: {
    marginTop: Space.xl,
    gap: Space.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    padding: Space.md,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Palette.border,
    backgroundColor: Palette.surface,
  },
  rowWin: {
    borderColor: Palette.primary,
    backgroundColor: Palette.primaryTint,
  },
  swatch: {
    width: 4,
    height: 44,
    borderRadius: Radius.pill,
  },
  rowBody: {
    flex: 1,
  },
  rowName: {
    ...Type.label,
    color: Palette.text,
  },
  rowMeta: {
    ...Type.caption,
    color: Palette.textMuted,
    marginTop: 2,
  },
  rowVerdict: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
    marginTop: 2,
    lineHeight: 13,
  },
  rowGrade: {
    ...Type.title,
    color: Palette.textMuted,
  },
  rowGradeWin: {
    color: Palette.primaryDeep,
  },
  footnote: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
    marginTop: Space.md,
  },
  footnoteText: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    flex: 1,
    lineHeight: 13,
  },
});
