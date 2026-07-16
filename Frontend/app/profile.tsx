import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { FuelCalculator } from '../components/trip/FuelCalculator';
import { Card, ScreenTitle, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { profiles } from '../constants/profiles';
import { districtByKey } from '../constants/districts';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

export default function ProfileScreen() {
  const { profileKey, setProfileKey, offline, toggleOffline, cachedAt, districtKey, source } =
    useTrip();
  const district = districtByKey(districtKey)!;
  const sourceLabel = {
    live: 'live GRU model output from the server',
    cache: 'cached model run stored on this device',
    synthetic: 'local baseline (server unreachable)',
  }[source];

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ScreenTitle
          title="Profile"
          subtitle="Your identity and travel setup. How you travel decides how every forecast is graded."
        />

        <SectionHeader title="Traveler type" />
        <View style={styles.profiles}>
          {profiles.map((p) => {
            const on = p.key === profileKey;
            return (
              <Pressable
                key={p.key}
                onPress={() => setProfileKey(p.key)}
                style={[styles.profile, on && styles.profileOn]}
              >
                <View style={[styles.profileIcon, on && styles.profileIconOn]}>
                  <Ionicons
                    name={p.icon as never}
                    size={17}
                    color={on ? Palette.onDark : Palette.primary}
                  />
                </View>
                <View style={styles.profileBody}>
                  <Text style={styles.profileName}>{p.name}</Text>
                  <Text style={styles.profileBlurb}>{p.blurb}</Text>
                  <Text style={styles.thresholds}>
                    Ideal {p.idealTemp[0]}–{p.idealTemp[1]}° · rain under {p.maxRain} mm · wind
                    under {p.maxWind} km/h
                  </Text>
                </View>
                {on ? (
                  <Ionicons name="checkmark-circle" size={20} color={Palette.primary} />
                ) : null}
              </Pressable>
            );
          })}
        </View>

        <View style={styles.section}>
          <SectionHeader title="Tuk-tuk fuel log" />
          <Card>
            <FuelCalculator districtKey={districtKey} />
          </Card>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Data & cache" />
          <Card>
            <View style={styles.switchRow}>
              <View style={styles.switchBody}>
                <Text style={styles.switchTitle}>Data saver</Text>
                <Text style={styles.switchMeta}>
                  Force the app to read the cached tensor instead of calling Open-Meteo.
                </Text>
              </View>
              <Switch
                value={offline}
                onValueChange={toggleOffline}
                trackColor={{ true: Palette.primary, false: Palette.border }}
                thumbColor={Palette.surface}
              />
            </View>

            <View style={styles.cacheRow}>
              <Ionicons name="save-outline" size={14} color={Palette.textDim} />
              <Text style={styles.cacheText}>
                Last checkpoint for {district.name}:{' '}
                {new Date(cachedAt).toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}{' '}
                — {sourceLabel}
              </Text>
            </View>
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  content: { padding: Space.lg, paddingBottom: Space.section },
  section: { marginTop: Space.section },
  profiles: { gap: Space.sm },
  profile: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Space.md,
    padding: Space.lg,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    backgroundColor: Palette.surface,
  },
  profileOn: { borderColor: Palette.primary, backgroundColor: Palette.primaryTint },
  profileIcon: {
    width: 34,
    height: 34,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileIconOn: { backgroundColor: Palette.primary },
  profileBody: { flex: 1 },
  profileName: { ...Type.label, color: Palette.text },
  profileBlurb: { ...Type.body, fontSize: 12, color: Palette.textMuted, marginTop: 2 },
  thresholds: { ...Type.caption, fontSize: 10, color: Palette.textDim, marginTop: 6 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  switchBody: { flex: 1 },
  switchTitle: { ...Type.label, color: Palette.text },
  switchMeta: { ...Type.body, fontSize: 12, color: Palette.textMuted, marginTop: 2 },
  cacheRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: Space.lg,
    paddingTop: Space.md,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  cacheText: { ...Type.caption, color: Palette.textDim },
  factRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  factDivider: {
    marginTop: Space.md,
    paddingTop: Space.md,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  factText: { ...Type.body, fontSize: 12, color: Palette.textMuted, flex: 1 },
});
