import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Comparer } from '../components/trip/Comparer';
import { HybridTimeline } from '../components/trip/HybridTimeline';
import { Banner, Card, ScreenTitle, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { suggestAlternative } from '../lib/engine';
import { Palette, Space, Type } from '../constants/trip-theme';

export default function PlanScreen() {
  const { districtKey, setDistrictKey, prediction, profileKey } = useTrip();
  const district = districtByKey(districtKey)!;
  const alternative = suggestAlternative(districtKey, prediction);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ScreenTitle
          title="Router"
          subtitle="Detour around heavy rain, compare destinations, plan the week ahead."
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
          <SectionHeader title="Compare two destinations" />
          <Card>
            <Comparer profileKey={profileKey} />
          </Card>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Climate-disruption planner" />
          <Card>
            <Text style={styles.explain}>
              Every day below is a GRU prediction for {district.name}. Day one reads 7 days of
              real observations; later days feed the model its own output plus the past week&apos;s
              hourly patterns, so confidence honestly decays the further out you look.
            </Text>
            <View style={styles.timeline}>
              <HybridTimeline district={district} />
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
  explain: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginBottom: Space.lg,
  },
  timeline: { marginTop: Space.xs },
});
