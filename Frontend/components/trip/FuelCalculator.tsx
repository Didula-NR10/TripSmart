import { useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fuelEfficiency, hillPenalty } from '../../lib/engine';
import { districtByKey } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export function FuelCalculator({ districtKey }: { districtKey: string }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [litres, setLitres] = useState('');

  const result = fuelEfficiency(Number(start), Number(end), Number(litres));
  const penalty = hillPenalty(districtKey);
  const district = districtByKey(districtKey);

  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Field label="Start odometer" value={start} onChange={setStart} suffix="km" />
        <Field label="End odometer" value={end} onChange={setEnd} suffix="km" />
      </View>
      <Field label="Fuel pumped" value={litres} onChange={setLitres} suffix="litres" />

      {result ? (
        <View style={styles.result}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{result.kmPerLitre}</Text>
            <Text style={styles.statLabel}>km / litre</Text>
          </View>
          <View style={styles.statRule} />
          <View style={styles.stat}>
            <Text style={styles.statValue}>{result.distance}</Text>
            <Text style={styles.statLabel}>km covered</Text>
          </View>
          <View style={styles.statRule} />
          <View style={styles.stat}>
            <Text style={styles.statValue}>{result.litresPer100}</Text>
            <Text style={styles.statLabel}>L / 100 km</Text>
          </View>
        </View>
      ) : (
        <Text style={styles.hint}>Enter both readings and litres pumped to calculate.</Text>
      )}

      {penalty > 0 ? (
        <View style={styles.alert}>
          <Ionicons name="trending-up-outline" size={14} color={Palette.warn} />
          <Text style={styles.alertText}>
            {district?.name} sits at {district?.elevation} m. Expect roughly {penalty}% higher
            consumption on sustained climbs.
          </Text>
        </View>
      ) : null}
    </View>
  );
}

function Field({
  label,
  value,
  onChange,
  suffix,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  suffix: string;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.inputWrap}>
        <TextInput
          value={value}
          onChangeText={onChange}
          keyboardType="numeric"
          placeholder="0"
          placeholderTextColor={Palette.textDim}
          style={styles.input}
        />
        <Text style={styles.suffix}>{suffix}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: Space.md,
  },
  row: {
    flexDirection: 'row',
    gap: Space.md,
  },
  field: {
    flex: 1,
    gap: 5,
  },
  fieldLabel: {
    ...Type.caption,
    color: Palette.textMuted,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
  },
  input: {
    flex: 1,
    height: 44,
    ...Type.label,
    color: Palette.text,
  },
  suffix: {
    ...Type.caption,
    color: Palette.textDim,
  },
  result: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Palette.primaryTint,
    borderRadius: Radius.md,
    paddingVertical: Space.lg,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontFamily: Type.title.fontFamily,
    fontSize: 20,
    color: Palette.primaryDeep,
  },
  statLabel: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.primary,
    marginTop: 2,
  },
  statRule: {
    width: 1,
    height: 28,
    backgroundColor: Palette.primarySoft,
  },
  hint: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textDim,
    textAlign: 'center',
    paddingVertical: Space.md,
  },
  alert: {
    flexDirection: 'row',
    gap: Space.sm,
    backgroundColor: Palette.warnSoft,
    borderRadius: Radius.md,
    padding: Space.md,
  },
  alertText: {
    ...Type.body,
    fontSize: 12,
    color: '#7A5A12',
    flex: 1,
  },
});
