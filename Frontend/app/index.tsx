import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { TodayHero } from '../components/trip/TodayHero';
import { HourStrip } from '../components/trip/HourStrip';
import { DistrictSheet } from '../components/trip/DistrictSheet';
import { DistrictMap, MapPin } from '../components/trip/DistrictMap';
import { Next24Strip, Next24Summary } from '../components/trip/Next24';
import { Banner, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { bestWindow, resolveDistrict, zonesNear } from '../lib/engine';
import { profileByKey } from '../constants/profiles';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

const fmtHour = (h: number) => {
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour} ${suffix}`;
};

export default function TodayScreen() {
  const router = useRouter();
  const {
    districtKey,
    setDistrictKey,
    prediction,
    profileKey,
    offline,
    forecast24,
    forecast24Loading,
    runForecast24,
  } = useTrip();
  const [picking, setPicking] = useState(false);
  const [selectedHour, setSelectedHour] = useState<number | null>(null);
  const [pinAdvisories, setPinAdvisories] = useState(0);
  const [pin, setPin] = useState<MapPin>(null);
  const [locationChosen, setLocationChosen] = useState(false);

  const district = districtByKey(districtKey)!;
  const profile = profileByKey(profileKey);
  const window = bestWindow(prediction, profile);
  const nowHour = new Date().getHours();
  const activeHour = selectedHour ?? nowHour;
  const now = prediction.hours[activeHour];

  const onPick = (lat: number, lng: number) => {
    setPin({ latitude: lat, longitude: lng });
    const found = resolveDistrict(lat, lng);
    if (found) {
      setDistrictKey(found.key);
    }
    setPinAdvisories(zonesNear(lat, lng).length);
    setLocationChosen(true);
  };

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, locationChosen && styles.contentWithCta]}
      >
        <TodayHero
          district={district}
          now={now}
          offline={offline}
          previewLabel={selectedHour !== null && selectedHour !== nowHour ? `Previewing ${fmtHour(selectedHour)}` : undefined}
          onPressDistrict={() => setPicking(true)}
        />

        {/* Hour-by-hour clock for the selected district, right under the hero. */}
        <View style={styles.section}>
          <SectionHeader
            title={`Today by the clock · ${district.name}`}
            action={selectedHour !== null ? 'Reset to now' : undefined}
            onPress={() => setSelectedHour(null)}
          />
          <HourStrip
            hours={prediction.hours}
            window={window}
            selectedHour={activeHour}
            onSelectHour={setSelectedHour}
          />
        </View>

        <View style={styles.banners}>
          {offline ? (
            <Banner
              tone="warn"
              icon="cloud-offline-outline"
              title="Showing cached prediction"
              body="No connection. This is the last model output stored on the device."
            />
          ) : null}

          {pinAdvisories > 0 ? (
            <Banner
              tone="danger"
              icon="warning-outline"
              title={`${pinAdvisories} legal advisory${pinAdvisories > 1 ? 'ies' : ''} near this pin`}
              body="Sacred site or restricted zone rules apply here."
              action="Read in Culture tab"
              onPress={() => router.push('/explore')}
            />
          ) : null}
        </View>

        <View style={styles.section}>
          <SectionHeader title="Pick a location" />
          <DistrictMap selected={district} pin={pin} onPick={onPick} />

          {/* Dropdown fallback when the map is unavailable or awkward */}
          <Pressable style={styles.dropdown} onPress={() => setPicking(true)}>
            <Ionicons name="list-outline" size={15} color={Palette.primary} />
            <View style={styles.dropdownBody}>
              <Text style={styles.dropdownLabel}>Or choose from 25 districts</Text>
              <Text style={styles.dropdownValue}>{district.name} District</Text>
            </View>
            <Ionicons name="chevron-down" size={16} color={Palette.textMuted} />
          </Pressable>
        </View>

        {forecast24 ? (
          <View style={styles.section}>
            <SectionHeader title={`Next 24 hours in ${district.name}`} />
            <Next24Strip forecast={forecast24} />
            <Next24Summary forecast={forecast24} />
          </View>
        ) : null}
      </ScrollView>

      {/* Predict button pinned above the tab bar once a location is chosen. */}
      {locationChosen ? (
        <View style={styles.ctaBar}>
          <Pressable
            style={[styles.forecastCta, forecast24Loading && styles.forecastCtaBusy]}
            onPress={runForecast24}
            disabled={forecast24Loading}
          >
            {forecast24Loading ? (
              <>
                <ActivityIndicator size="small" color={Palette.onDark} />
                <Text style={styles.forecastCtaText}>Running the model…</Text>
              </>
            ) : (
              <>
                <Ionicons name="cloud-download-outline" size={17} color={Palette.onDark} />
                <Text style={styles.forecastCtaText}>Next 24 Hours Weather</Text>
              </>
            )}
          </Pressable>
        </View>
      ) : null}

      <DistrictSheet
        visible={picking}
        onClose={() => setPicking(false)}
        onSelect={(key) => {
          setDistrictKey(key);
          setPinAdvisories(0);
          setPin(null);
          setLocationChosen(true);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: Palette.canvas,
  },
  content: {
    paddingBottom: Space.section,
  },
  contentWithCta: {
    // Keep the last section reachable above the pinned predict button.
    paddingBottom: Space.section + 64,
  },
  banners: {
    paddingHorizontal: Space.lg,
    marginTop: Space.lg,
    gap: Space.sm,
  },
  section: {
    marginTop: Space.section,
    paddingHorizontal: Space.lg,
  },
  dropdown: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    marginTop: Space.sm,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
  },
  dropdownBody: {
    flex: 1,
  },
  dropdownLabel: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
  dropdownValue: {
    ...Type.label,
    color: Palette.text,
    marginTop: 1,
  },
  ctaBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: Space.lg,
    paddingTop: Space.sm,
    paddingBottom: Space.md,
    backgroundColor: Palette.canvas,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  forecastCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    backgroundColor: Palette.primary,
    borderRadius: Radius.md,
    paddingVertical: Space.md + 2,
  },
  forecastCtaBusy: {
    opacity: 0.8,
  },
  forecastCtaText: {
    ...Type.label,
    color: Palette.onDark,
  },
});
