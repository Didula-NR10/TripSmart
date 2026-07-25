import { useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { AuthPanel } from '../components/trip/AuthPanel';
import { NotificationInbox } from '../components/trip/NotificationInbox';
import { PageHero } from '../components/trip/PageHero';
import { ProfileOverview } from '../components/trip/ProfileOverview';
import { QuickActions } from '../components/trip/QuickActions';
import { TravelNotebook } from '../components/trip/TravelNotebook';
import { TravelSummaryStats } from '../components/trip/TravelSummaryStats';
import { SectionHeader } from '../components/trip/Ui';
import { TravelNote } from '../lib/api';
import { useAuth } from '../lib/auth';
import { getNotificationHistory, subscribeNotificationHistory } from '../lib/notify';
import { districts } from '../constants/districts';
import { Palette, Radius, Shadow, Space } from '../constants/trip-theme';

const NOTEBOOK_PREVIEW_COUNT = 2;
const HERO_IMAGE =
  'https://upload.wikimedia.org/wikipedia/commons/2/29/Hikers_watching_sunrise_at_Mount_Pulag_summit.jpg';

export default function ProfileScreen() {
  const { user } = useAuth();
  const [notes, setNotes] = useState<TravelNote[]>([]);
  const [notebookExpanded, setNotebookExpanded] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    getNotificationHistory().then((entries) => setUnread(entries.filter((e) => !e.read).length));
    return subscribeNotificationHistory((entries) =>
      setUnread(entries.filter((e) => !e.read).length),
    );
  }, []);

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
        <PageHero
          icon="person"
          title="Profile"
          subtitle={
            user
              ? 'Your account and your travel notebook.'
              : 'Log in or create an account to predict, compare districts and post ground reports.'
          }
          image={{ uri: HERO_IMAGE }}
          topRight={
            <>
              <Pressable
                style={styles.iconButton}
                onPress={() => Alert.alert('Settings', 'Account and app settings are coming soon.')}
                accessibilityLabel="Settings"
                hitSlop={6}
              >
                <Ionicons name="settings-outline" size={18} color={Palette.text} />
              </Pressable>
              <Pressable
                style={styles.iconButton}
                onPress={() => setInboxOpen(true)}
                accessibilityLabel="Notifications"
                hitSlop={6}
              >
                <Ionicons name="notifications-outline" size={18} color={Palette.text} />
                {unread > 0 ? <View style={styles.dot} /> : null}
              </Pressable>
            </>
          }
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
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadow.soft,
  },
  dot: {
    position: 'absolute',
    top: 7,
    right: 8,
    width: 9,
    height: 9,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primary,
    borderWidth: 1.5,
    borderColor: Palette.surface,
  },
});
