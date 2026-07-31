import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Comparer } from '../components/trip/Comparer';
import { HybridTimeline } from '../components/trip/HybridTimeline';
import { PageHero } from '../components/trip/PageHero';
import { Banner, Card, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { heroForDistrict } from '../constants/district-hero';
import { suggestAlternative } from '../lib/engine';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

const FOOTER: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  caption: string;
}[] = [
  { icon: 'rainy-outline', title: 'Smart routing', caption: 'Avoid heavy rain and delays' },
  { icon: 'shield-checkmark-outline', title: 'Accurate data', caption: 'Powered by WeatherAPI' },
  { icon: 'calendar-outline', title: 'Plan weekly', caption: '7-day outlook with confidence' },
  { icon: 'compass-outline', title: 'Travel better', caption: 'Make smarter decisions' },
];

export default function PlanScreen() {
  const { districtKey, setDistrictKey, prediction, profileKey } = useTrip();
  const district = districtByKey(districtKey)!;
  const alternative = suggestAlternative(districtKey, prediction);
  const [showWeek, setShowWeek] = useState(false);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <PageHero
          icon="navigate"
          title="Route Intelligence"
          subtitle="Compare destinations, avoid bad weather, and plan the smartest route."
          image={{ uri: heroForDistrict('nuwaraeliya').url }}
        />

        {alternative ? (
          <Banner
            tone="primary"
            icon="swap-horizontal-outline"
            title={`Consider ${alternative.district.name} instead`}
            body={`Heavy rain predicted in ${district.name} today. ${alternative.district.name} is ${alternative.driveKm} km away with only ${alternative.rain} mm forecast.`}
            action="Switch district"
            onPress={() => setDistrictKey(alternative.district.key)}
          />
        ) : null}

        <View style={alternative ? styles.section : undefined}>
          <SectionHeader title="Compare two destinations" icon="scale-balance" iconLib="mci" />
          <Card>
            <Comparer profileKey={profileKey} />
          </Card>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Climate-disruption planner" icon="bar-chart-outline" />
          <Card style={styles.plannerCard}>
            <View style={styles.plannerText}>
              <Text style={styles.plannerHeadline}>Plan ahead. Stay ahead.</Text>
              <Text style={styles.plannerBody}>
                Every day below is a GRU prediction for {district.name}. Day one reads 7 days of
                real observations; later days feed the model its own output plus the past
                week&apos;s hourly patterns, so confidence honestly decays the further out you
                look.
              </Text>
            </View>
            <Image
              source={{ uri: heroForDistrict('mannar').url }}
              style={styles.plannerImage}
              resizeMode="cover"
            />
          </Card>

          <Pressable style={styles.plannerCta} onPress={() => setShowWeek((v) => !v)}>
            <Ionicons name="trending-up-outline" size={17} color={Palette.onDark} />
            <Text style={styles.plannerCtaText}>
              {showWeek ? 'Hide the week' : `Analyse the week in ${district.name}`}
            </Text>
            <Ionicons
              name={showWeek ? 'chevron-up' : 'chevron-forward'}
              size={16}
              color={Palette.onDark}
            />
          </Pressable>

          {showWeek ? (
            <Card style={styles.timelineCard}>
              <HybridTimeline district={district} />
            </Card>
          ) : null}
        </View>

        <View style={styles.footerGrid}>
          {FOOTER.map((f) => (
            <View key={f.title} style={styles.footerItem}>
              <View style={styles.footerIcon}>
                <Ionicons name={f.icon} size={18} color={Palette.primaryDeep} />
              </View>
              <Text style={styles.footerTitle}>{f.title}</Text>
              <Text style={styles.footerCaption}>{f.caption}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  content: { padding: Space.lg, paddingBottom: Space.section },
  section: { marginTop: Space.section },
  plannerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
  },
  plannerText: { flex: 1 },
  plannerHeadline: {
    ...Type.label,
    fontSize: 17,
    color: Palette.text,
  },
  plannerBody: {
    ...Type.body,
    fontSize: 12,
    lineHeight: 17,
    color: Palette.textMuted,
    marginTop: Space.sm,
  },
  plannerImage: {
    width: 84,
    height: 96,
    borderRadius: Radius.md,
  },
  plannerCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    marginTop: Space.md,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryDeep,
  },
  plannerCtaText: {
    ...Type.label,
    color: Palette.onDark,
  },
  timelineCard: {
    marginTop: Space.md,
  },
  footerGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: Space.section,
  },
  footerItem: {
    width: '25%',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  footerIcon: {
    width: 44,
    height: 44,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.sm,
  },
  footerTitle: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
    textAlign: 'center',
  },
  footerCaption: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
    textAlign: 'center',
    marginTop: 2,
  },
});
