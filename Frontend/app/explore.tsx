import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { ZoneModal } from '../components/trip/ZoneModal';
import { DistrictSheet } from '../components/trip/DistrictSheet';
import { LawGuide } from '../components/trip/LawGuide';
import { SpecialtyGuide } from '../components/trip/SpecialtyGuide';
import { Banner, ScreenTitle, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { Zone, zones } from '../constants/geofences';
import { allLaws, lawsForDistrict } from '../constants/laws';
import { allSpecialties, specialtiesForDistrict } from '../constants/specialties';
import { notifyDistrictEntered } from '../lib/notify';
import { poyaToday, resolveDistrict, zonesInDistrict } from '../lib/engine';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

export default function ExploreScreen() {
  const { districtKey, setDistrictKey } = useTrip();
  const [zone, setZone] = useState<Zone | null>(null);
  const [locating, setLocating] = useState(false);
  const [locStatus, setLocStatus] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  // Page filter: a district key, or 'all' for the island-wide view. Follows
  // the app-wide district (GPS or other tabs) until the user picks manually.
  const [filterKey, setFilterKey] = useState<string>(districtKey);
  const watcher = useRef<Location.LocationSubscription | null>(null);

  useEffect(() => {
    setFilterKey(districtKey);
  }, [districtKey]);

  // Stop watching GPS when the screen unmounts.
  useEffect(
    () => () => {
      watcher.current?.remove();
    },
    [],
  );

  const isAll = filterKey === 'all';
  const filterName = isAll ? 'All Sri Lanka' : districtByKey(filterKey)?.name ?? filterKey;
  const poya = poyaToday();
  const shownZones = isAll ? zones : zonesInDistrict(filterKey);
  const laws = isAll ? allLaws() : lawsForDistrict(filterKey);
  const specialties = isAll ? allSpecialties() : specialtiesForDistrict(filterKey);

  const applyFix = (lat: number, lng: number): boolean => {
    const found = resolveDistrict(lat, lng);
    if (!found) return false;
    setDistrictKey(found.key);
    notifyDistrictEntered(found.key);
    return true;
  };

  const useMyLocation = async () => {
    setLocating(true);
    setLocStatus(null);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocStatus('Location permission denied — pick a district manually instead.');
        return;
      }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      if (!applyFix(pos.coords.latitude, pos.coords.longitude)) {
        setLocStatus('You appear to be outside Sri Lanka — pick a district manually.');
        return;
      }
      setLocStatus(
        'Following your location. Crossing a district notifies you, then one law or specialty every 30 minutes.',
      );

      // Keep following while the app is open: crossing into a new district
      // re-resolves it and fires the entry notification.
      watcher.current?.remove();
      watcher.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.Balanced, distanceInterval: 1000 },
        (p) => applyFix(p.coords.latitude, p.coords.longitude),
      );
    } catch {
      setLocStatus('Could not get a location fix. Pick a district manually.');
    } finally {
      setLocating(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ScreenTitle
          title="Culture"
          subtitle="Laws, etiquette and local specialties for wherever you are right now."
        />

        <Pressable style={styles.locate} onPress={useMyLocation} disabled={locating}>
          {locating ? (
            <ActivityIndicator size="small" color={Palette.primary} />
          ) : (
            <Ionicons name="locate-outline" size={17} color={Palette.primary} />
          )}
          <View style={styles.locateBody}>
            <Text style={styles.locateTitle}>
              {locating ? 'Finding you…' : 'Use my location'}
            </Text>
            <Text style={styles.locateMeta}>
              {locStatus ?? 'Tap to auto-detect your district and get local notifications.'}
            </Text>
          </View>
        </Pressable>

        {/* ── district filter: 25 districts + All Sri Lanka ─────────────── */}
        <Pressable style={styles.filter} onPress={() => setPicking(true)}>
          <Ionicons name="funnel-outline" size={15} color={Palette.primaryDeep} />
          <View style={styles.locateBody}>
            <Text style={styles.filterLabel}>Filtering by</Text>
            <Text style={styles.filterValue}>{filterName}</Text>
          </View>
          <Ionicons name="chevron-down" size={15} color={Palette.textMuted} />
        </Pressable>

        <View style={styles.section}>
          <SectionHeader title={`Advisories · ${filterName}`} />
          <View style={styles.banners}>
            {poya ? (
              <Banner
                tone="warn"
                icon="moon-outline"
                title={`Today is ${poya.name}`}
                body="Public sale of alcohol and meat is legally restricted across Sri Lanka. Bars and many restaurants close."
              />
            ) : null}

            {shownZones.map((z) => (
              <Banner
                key={z.key}
                tone={z.kind === 'restricted' ? 'danger' : 'primary'}
                icon={z.kind === 'restricted' ? 'warning-outline' : 'hand-left-outline'}
                title={z.name}
                body={
                  z.kind === 'restricted'
                    ? 'Restricted airspace or security zone. Tap to read the rules.'
                    : 'Sacred site. Tap to read the etiquette and legal requirements.'
                }
                action="Read rules"
                onPress={() => setZone(z)}
              />
            ))}

            {!poya && shownZones.length === 0 ? (
              <Banner
                tone="primary"
                icon="checkmark-circle-outline"
                title="No zone advisories in this district"
                body="General laws and customs below still apply throughout your stay."
              />
            ) : null}
          </View>
        </View>

        <View style={styles.section}>
          <SectionHeader title={`Laws & customs · ${filterName}`} />
          <LawGuide laws={laws} districtName={isAll ? null : filterName} />
        </View>

        <View style={styles.section}>
          <SectionHeader title={`Famous in ${filterName}`} />
          <SpecialtyGuide items={specialties} districtName={isAll ? null : filterName} />
        </View>
      </ScrollView>

      <ZoneModal zone={zone} onClose={() => setZone(null)} />

      <DistrictSheet
        visible={picking}
        onClose={() => setPicking(false)}
        onSelect={setFilterKey}
        title="Filter by district"
        allOption
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Palette.canvas,
  },
  content: {
    padding: Space.lg,
    paddingBottom: Space.section,
  },
  locate: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    backgroundColor: Palette.primaryTint,
    borderWidth: 1,
    borderColor: Palette.primary,
    borderStyle: 'dashed',
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
  },
  locateBody: { flex: 1 },
  locateTitle: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primaryDeep,
  },
  locateMeta: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
    marginTop: 2,
  },
  filter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
    marginTop: Space.sm,
  },
  filterLabel: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
  },
  filterValue: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
    marginTop: 1,
  },
  banners: {
    gap: Space.sm,
  },
  section: {
    marginTop: Space.section,
  },
});
