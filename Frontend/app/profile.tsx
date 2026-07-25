import { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthPanel } from '../components/trip/AuthPanel';
import { NotificationInbox } from '../components/trip/NotificationInbox';
import { ProfileHero } from '../components/trip/ProfileHero';
import { ProfileOverview } from '../components/trip/ProfileOverview';
import { QuickActions } from '../components/trip/QuickActions';
import { TravelNotebook } from '../components/trip/TravelNotebook';
import { TravelSummaryStats } from '../components/trip/TravelSummaryStats';
import { SectionHeader } from '../components/trip/Ui';
import { TravelNote } from '../lib/api';
import { useAuth } from '../lib/auth';
import { districts } from '../constants/districts';
import { Palette, Space } from '../constants/trip-theme';

const NOTEBOOK_PREVIEW_COUNT = 2;

export default function ProfileScreen() {
  const { user } = useAuth();
  const [notes, setNotes] = useState<TravelNote[]>([]);
  const [notebookExpanded, setNotebookExpanded] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);

  // There is no gamification backend — these are honest, derived reads of
  // the traveller's own notebook, not server-tracked stats.
  const stats = useMemo(() => {
    const places = new Set(
      notes.map((n) => n.place.trim().toLowerCase()).filter(Boolean),
    );
    const regions = new Set(
      notes.flatMap((n) => {
        const p = n.place.toLowerCase();
        return districts.filter((d) => p.includes(d.name.toLowerCase())).map((d) => d.key);
      }),
    );
    const notesWritten = notes.length;
    const travelPoints = places.size * 150 + notesWritten * 50;
    return { placesVisited: places.size, notesWritten, regionsExplored: regions.size, travelPoints };
  }, [notes]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ProfileHero
          title="Profile"
          subtitle={
            user
              ? 'Your account and your travel notebook.'
              : 'Log in or create an account to predict, compare districts and post ground reports.'
          }
          onPressNotifications={() => setInboxOpen(true)}
        />

        {user ? (
          <>
            <ProfileOverview travelPoints={stats.travelPoints} />

            <View style={styles.section}>
              <TravelSummaryStats
                stats={[
                  { iconLib: 'ion', icon: 'location', value: String(stats.placesVisited), label: 'Places visited' },
                  { iconLib: 'ion', icon: 'document-text', value: String(stats.notesWritten), label: 'Notes written' },
                  { iconLib: 'mci', icon: 'image-filter-hdr', value: String(stats.regionsExplored), label: 'Regions explored' },
                  { iconLib: 'ion', icon: 'star', value: stats.travelPoints.toLocaleString(), label: 'Travel points' },
                ]}
              />
            </View>

            <View style={styles.section}>
              <SectionHeader
                title="Travel notebook"
                action={
                  notes.length > NOTEBOOK_PREVIEW_COUNT
                    ? notebookExpanded
                      ? 'Show less'
                      : 'View all'
                    : undefined
                }
                onPress={() => setNotebookExpanded((e) => !e)}
              />
              <TravelNotebook
                limit={notebookExpanded ? undefined : NOTEBOOK_PREVIEW_COUNT}
                onNotesChange={setNotes}
              />
            </View>

            <View style={styles.section}>
              <SectionHeader title="Quick actions" />
              <QuickActions />
            </View>
          </>
        ) : (
          <View style={styles.section}>
            <AuthPanel />
          </View>
        )}
      </ScrollView>

      <NotificationInbox visible={inboxOpen} onClose={() => setInboxOpen(false)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  content: { padding: Space.lg, paddingBottom: Space.section },
  section: { marginTop: Space.section },
});
