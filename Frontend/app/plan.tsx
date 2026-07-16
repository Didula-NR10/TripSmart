import { ScrollView, StyleSheet, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Comparer } from '../components/trip/Comparer';
import { HybridTimeline } from '../components/trip/HybridTimeline';
import { Banner, Card, Empty, ScreenTitle, SectionHeader } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { districtByKey } from '../constants/districts';
import { bestWindow, gradeDay, predict, suggestAlternative } from '../lib/engine';
import { profileByKey } from '../constants/profiles';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

export default function PlanScreen() {
  const { districtKey, setDistrictKey, prediction, profileKey, watches, toggleWatch } = useTrip();
  const district = districtByKey(districtKey)!;
  const profile = profileByKey(profileKey);
  const watching = watches.some((w) => w.districtKey === districtKey);
  const alternative = suggestAlternative(districtKey, prediction);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ScreenTitle
          title="Router"
          subtitle="Detour around heavy rain, compare destinations, watch for a clear window."
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
              Day one comes from the GRU model. Later days fall back to the 10-year statistical
              baseline for {district.name}, because no model predicts that far out honestly.
            </Text>
            <View style={styles.timeline}>
              <HybridTimeline district={district} prediction={prediction} />
            </View>
          </Card>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Watchlist" />
          <Card>
            <Pressable style={styles.watchRow} onPress={() => toggleWatch(districtKey)}>
              <View style={styles.watchIcon}>
                <Ionicons
                  name={watching ? 'eye' : 'eye-outline'}
                  size={17}
                  color={Palette.primary}
                />
              </View>
              <View style={styles.watchBody}>
                <Text style={styles.watchTitle}>{district.name}</Text>
                <Text style={styles.watchMeta}>
                  {watching
                    ? 'Watching. Re-scored each time you open the app.'
                    : 'Tap to watch this district for a clear window.'}
                </Text>
              </View>
              <Ionicons
                name={watching ? 'checkmark-circle' : 'add-circle-outline'}
                size={21}
                color={watching ? Palette.primary : Palette.textDim}
              />
            </Pressable>

            {watches.length === 0 ? (
              <Empty text="Nothing watched yet." />
            ) : (
              watches
                .filter((w) => w.districtKey !== districtKey)
                .map((w) => {
                  const d = districtByKey(w.districtKey)!;
                  const p = predict(w.districtKey);
                  const g = gradeDay(p, profileKey);
                  const win = bestWindow(p, profile);
                  return (
                    <View key={w.districtKey} style={styles.watched}>
                      <View style={styles.watchBody}>
                        <Text style={styles.watchTitle}>{d.name}</Text>
                        <Text style={styles.watchMeta}>
                          {win ? `Clear window ${win.from}:00 – ${win.to}:00` : 'No clear window'}
                        </Text>
                      </View>
                      <Text style={styles.grade}>{g.letter}</Text>
                    </View>
                  );
                })
            )}

            <View style={styles.note}>
              <Ionicons name="information-circle-outline" size={13} color={Palette.textDim} />
              <Text style={styles.noteText}>
                Mobile operating systems throttle background execution, so this re-scores on app
                open rather than on a server cron loop.
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
  explain: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginBottom: Space.lg,
  },
  timeline: { marginTop: Space.xs },
  watchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    paddingBottom: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.borderSoft,
  },
  watchIcon: {
    width: 34,
    height: 34,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  watchBody: { flex: 1 },
  watchTitle: { ...Type.label, color: Palette.text },
  watchMeta: { ...Type.caption, color: Palette.textMuted, marginTop: 2 },
  watched: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.borderSoft,
  },
  grade: { ...Type.title, color: Palette.primaryDeep },
  note: {
    flexDirection: 'row',
    gap: 6,
    marginTop: Space.md,
  },
  noteText: {
    ...Type.caption,
    color: Palette.textDim,
    flex: 1,
    lineHeight: 15,
  },
});
