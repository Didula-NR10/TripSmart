import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { ZoneModal } from '../components/trip/ZoneModal';
import { DistrictSheet } from '../components/trip/DistrictSheet';
import { LawGuide } from '../components/trip/LawGuide';
import { PageHero } from '../components/trip/PageHero';
import { SpecialtyGuide } from '../components/trip/SpecialtyGuide';
import { Banner, FilterRow, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { heroForDistrict, WIKIMEDIA_IMAGE_HEADERS } from '../constants/district-hero';
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

  const heroImage = {
    uri: heroForDistrict(isAll ? 'colombo' : filterKey).url,
    headers: WIKIMEDIA_IMAGE_HEADERS,
  };

  return (
    <SafeAreaView style={styles.safe} edges={[]}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <PageHero
          icon="business"
          title="Local Guide"
          subtitle="Essential laws, etiquette & local guidelines for a safe and respectful trip."
          image={heroImage}
        />

        <Pressable style={styles.locate} onPress={useMyLocation} disabled={locating}>
          <View style={styles.locateIcon}>
            {locating ? (
              <ActivityIndicator size="small" color={Palette.primaryDeep} />
            ) : (
              <Ionicons name="locate" size={17} color={Palette.primaryDeep} />
            )}
          </View>
          <View style={styles.locateBody}>
            <Text style={styles.locateTitle}>
              {locating ? 'Finding you…' : 'Use my location'}
            </Text>
            <Text style={styles.locateMeta}>
              {locStatus ?? 'Tap to auto-detect your district and get local notifications.'}
            </Text>
          </View>
          <View style={styles.locateGo}>
            <Ionicons name="chevron-forward" size={17} color={Palette.onDark} />
          </View>
        </Pressable>

        {/* ── district filter: 25 districts + All Sri Lanka ─────────────── */}
        <View style={styles.filterWrap}>
          <FilterRow label="Filtering by" value={filterName} onPress={() => setPicking(true)} />
        </View>

        <View style={styles.section}>
          <SectionHeader
            title={`Advisories · ${filterName}`}
            icon="shield-outline"
            iconTone="danger"
            action="View all"
            actionTone="danger"
          />
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
          <SectionHeader
            title={`Laws & guidelines · ${filterName}`}
            icon="scale-balance"
            iconLib="mci"
          />
          <LawGuide laws={laws} districtName={isAll ? null : filterName} />
        </View>

        <View style={styles.section}>
          <SectionHeader title={`Famous in ${filterName}`} />
          <SpecialtyGuide items={specialties} districtName={isAll ? null : filterName} />
        </View>

        <Pressable style={styles.closingBanner}>
          <View style={styles.closingIcon}>
            <Ionicons name="shield-checkmark" size={20} color={Palette.onDark} />
          </View>
          <View style={styles.closingBody}>
            <Text style={styles.closingTitle}>Travel smart. Respect local rules.</Text>
            <Text style={styles.closingMeta}>Stay informed, stay safe, and enjoy your journey.</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={Palette.onDark} />
        </Pressable>
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
    borderRadius: Radius.lg,
    paddingHorizontal: Space.lg,
    paddingVertical: Space.lg,
  },
  locateIcon: {
    width: 40,
    height: 40,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  locateBody: { flex: 1 },
  locateTitle: {
    ...Type.label,
    fontSize: 15,
    color: Palette.text,
  },
  locateMeta: {
    ...Type.body,
    fontSize: 12,
    lineHeight: 16,
    color: Palette.textMuted,
    marginTop: 2,
  },
  locateGo: {
    width: 34,
    height: 34,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryDeep,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterWrap: {
    marginTop: Space.md,
  },
  banners: {
    gap: Space.sm,
  },
  section: {
    marginTop: Space.section,
  },
  closingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    backgroundColor: Palette.primaryDeep,
    borderRadius: Radius.lg,
    padding: Space.lg,
    marginTop: Space.section,
  },
  closingIcon: {
    width: 40,
    height: 40,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  closingBody: { flex: 1 },
  closingTitle: {
    ...Type.label,
    fontSize: 15,
    color: Palette.onDark,
  },
  closingMeta: {
    ...Type.caption,
    fontSize: 12,
    color: Palette.onDarkMuted,
    marginTop: 2,
  },
});
