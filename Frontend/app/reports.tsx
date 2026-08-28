import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { DistrictSheet } from '../components/trip/DistrictSheet';
import { PageHero } from '../components/trip/PageHero';
import { FilterRow } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { useAuth, useAuthGate } from '../lib/auth';
import { districtByKey } from '../constants/districts';
import { heroForDistrict, WIKIMEDIA_IMAGE_HEADERS } from '../constants/district-hero';
import {
  GroundReport,
  deleteGroundReport,
  fetchGroundReports,
  postGroundReport,
  reverseGeocode,
} from '../lib/api';
import { getCachedPushToken } from '../lib/notify';
import { resolveDistrict } from '../lib/engine';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

const SHOW_LOCATION_SHARE = false;

const ago = (at: number) => {
  const mins = Math.max(1, Math.round((Date.now() - at) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  return `${hrs}h ago`;
};

const postedAt = (at: number) =>
  new Date(at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

export default function ReportsScreen() {
  const { districtKey } = useTrip();
  const gate = useAuthGate();
  const { user } = useAuth();

  const [reports, setReports] = useState<GroundReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [failed, setFailed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // filter + search
  const [filterKey, setFilterKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // report form (4 fields: district, location, title, detail)
  const [composing, setComposing] = useState(false);
  const [formDistrict, setFormDistrict] = useState(districtKey);
  const [location, setLocation] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [posting, setPosting] = useState(false);

  // Share current location: GPS fix -> nearest town/city/village, prefilling
  // "Where exactly" (still editable after) — the alternative to typing it in
  // manually, which the field already supports on its own.
  const [resolvingLocation, setResolvingLocation] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  // which selector the district sheet is feeding
  const [sheetTarget, setSheetTarget] = useState<'filter' | 'form' | null>(null);

  const load = useCallback(async (districtFilter: string | null, query: string) => {
    setLoading(true);
    try {
      const data = await fetchGroundReports({
        districtKey: districtFilter ?? undefined,
        search: query || undefined,
      });
      setReports(data);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // Search is debounced so we don't hit the server per keystroke.
  useEffect(() => {
    const t = setTimeout(() => load(filterKey, search), 350);
    return () => clearTimeout(t);
  }, [filterKey, search, load]);

  // Pull-to-refresh: re-fetch without swapping the list for the full-screen spinner.
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load(filterKey, search);
    } finally {
      setRefreshing(false);
    }
  }, [load, filterKey, search]);

  // "Share current location": GPS fix on wherever the user is standing right
  // now (no picking on a map) -> re-resolves the district it falls in and
  // looks up the nearest town/city/village to prefill "Where exactly" with.
  // Typing it in manually (the field itself) is the other option.
  const shareCurrentLocation = async () => {
    setLocationError(null);
    setResolvingLocation(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocationError('Location permission denied — enter it manually instead.');
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const { latitude, longitude } = pos.coords;

      const found = resolveDistrict(latitude, longitude);
      if (found) setFormDistrict(found.key);

      const result = await reverseGeocode(latitude, longitude);
      setLocation(result.placeName);
    } catch {
      setLocationError('Could not detect your location — enter it manually instead.');
    } finally {
      setResolvingLocation(false);
    }
  };

  const submit = async () => {
    if (!location.trim() || !title.trim()) return;
    if (!gate()) return; // token may have expired since the form opened
    setPosting(true);
    try {
      const excludeToken = (await getCachedPushToken()) ?? undefined;
      await postGroundReport({
        districtKey: formDistrict,
        location: location.trim(),
        title: title.trim(),
        body: body.trim(),
        excludeToken,
      });
      setLocation('');
      setTitle('');
      setBody('');
      setComposing(false);
      setLocationError(null);
      await load(filterKey, search);
    } catch {
      setFailed(true);
    } finally {
      setPosting(false);
    }
  };

  const removeReport = async (id: string) => {
    if (!gate()) return; // session may have expired since page load
    const previous = reports;
    setDeletingId(id);
    setReports((rs) => rs.filter((r) => r.id !== id)); // optimistic
    try {
      await deleteGroundReport(id);
    } catch {
      setReports(previous); // restore on failure
    } finally {
      setDeletingId(null);
    }
  };

  const filterDistrict = filterKey ? districtByKey(filterKey) : null;
  const filtering = filterKey !== null || search.trim() !== '';

  return (
    <SafeAreaView style={styles.safe} edges={[]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[Palette.primary]}
            tintColor={Palette.primary}
          />
        }
      >
        <PageHero
          icon="chatbubbles"
          title="Ground Reports"
          subtitle="Live conditions from travellers on the ground. Every report expires after 24 hours."
          image={{ uri: heroForDistrict('badulla').url, headers: WIKIMEDIA_IMAGE_HEADERS }}
        />

        {composing ? (
          <View style={styles.form}>
            {/* 1 — district */}
            <Pressable style={styles.formDistrict} onPress={() => setSheetTarget('form')}>
              <Ionicons name="location-outline" size={15} color={Palette.primary} />
              <View style={styles.formDistrictBody}>
                <Text style={styles.fieldLabel}>District</Text>
                <Text style={styles.formDistrictValue}>
                  {districtByKey(formDistrict)?.name ?? formDistrict}
                </Text>
              </View>
              <Ionicons name="chevron-down" size={14} color={Palette.textMuted} />
            </Pressable>

            {/* 2 — exact location */}
            <TextInput
              value={location}
              onChangeText={setLocation}
              placeholder="Where exactly? e.g. Ella Rock trail, Galle Face Green"
              placeholderTextColor={Palette.textDim}
              style={styles.input}
            />

            {SHOW_LOCATION_SHARE ? (
              <>
                <Pressable
                  style={styles.shareLocation}
                  onPress={shareCurrentLocation}
                  disabled={resolvingLocation}
                >
                  {resolvingLocation ? (
                    <ActivityIndicator size="small" color={Palette.primary} />
                  ) : (
                    <Ionicons name="navigate" size={14} color={Palette.primary} />
                  )}
                  <Text style={styles.shareLocationText}>
                    {resolvingLocation ? 'Finding your location…' : 'Share current location'}
                  </Text>
                </Pressable>
                <Text style={styles.shareLocationHint}>or type it in above manually</Text>
              </>
            ) : null}

            {locationError ? <Text style={styles.locationError}>{locationError}</Text> : null}

            {/* 3 — the main point */}
            <TextInput
              value={title}
              onChangeText={setTitle}
              placeholder="What did you see on the ground?"
              placeholderTextColor={Palette.textDim}
              style={styles.input}
            />

            {/* 4 — detail */}
            <TextInput
              value={body}
              onChangeText={setBody}
              placeholder="Detail. Trail conditions, closures, queue times."
              placeholderTextColor={Palette.textDim}
              multiline
              style={[styles.input, styles.multiline]}
            />

            <View style={styles.formActions}>
              <Pressable
                onPress={() => {
                  setComposing(false);
                  setLocationError(null);
                }}
                style={styles.cancel}
              >
                <Text style={styles.cancelText}>Cancel</Text>
              </Pressable>
              <Pressable
                onPress={submit}
                disabled={posting || !location.trim() || !title.trim()}
                style={[styles.submit, (posting || !location.trim() || !title.trim()) && styles.submitOff]}
              >
                {posting ? (
                  <ActivityIndicator size="small" color={Palette.onDark} />
                ) : (
                  <Text style={styles.submitText}>Post report</Text>
                )}
              </Pressable>
            </View>
          </View>
        ) : (
          <Pressable
            style={styles.trigger}
            onPress={() => {
              if (!gate()) return; // posting reports needs an account
              setFormDistrict(districtKey);
              setComposing(true);
            }}
          >
            <View style={styles.triggerIcon}>
              <Ionicons name="cloud-upload-outline" size={19} color={Palette.primaryDeep} />
            </View>
            <View style={styles.triggerBody}>
              <Text style={styles.triggerText}>Report ground conditions here</Text>
              <Text style={styles.triggerMeta}>
                Help fellow travellers by sharing real-time updates.
              </Text>
            </View>
            <View style={styles.triggerGo}>
              <Ionicons name="chevron-forward" size={17} color={Palette.onDark} />
            </View>
          </Pressable>
        )}

        {/* filter + clear */}
        <View style={styles.filterWrap}>
          <FilterRow
            label={filtering ? 'Filtering by' : 'Districts'}
            value={filterDistrict ? filterDistrict.name : 'All districts'}
            onPress={() => setSheetTarget('filter')}
          />
          {filtering ? (
            <Pressable
              style={styles.clear}
              onPress={() => {
                setFilterKey(null);
                setSearch('');
              }}
            >
              <Ionicons name="close-circle" size={14} color={Palette.danger} />
              <Text style={styles.clearText}>Clear filters</Text>
            </Pressable>
          ) : null}
        </View>

        <View style={styles.search}>
          <Ionicons name="search" size={15} color={Palette.textDim} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="Search reports — e.g. rain, closed, queue"
            placeholderTextColor={Palette.textDim}
            style={styles.searchInput}
          />
          {search ? (
            <Pressable onPress={() => setSearch('')} hitSlop={8}>
              <Ionicons name="close" size={15} color={Palette.textDim} />
            </Pressable>
          ) : null}
        </View>

        {/* the feed */}
        {loading && reports.length === 0 ? (
          <View style={styles.loading}>
            <ActivityIndicator color={Palette.primary} />
          </View>
        ) : failed ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>Can&apos;t reach the server</Text>
            <Text style={styles.emptySubtitle}>Ground reports need a connection. Try again shortly.</Text>
          </View>
        ) : reports.length === 0 ? (
          <View style={styles.emptyCard}>
            <View style={styles.emptyCircle}>
              <View style={styles.emptyPost} />
              <View style={styles.emptySign} />
              <View style={[styles.emptyBush, styles.emptyBushLeft]} />
              <View style={[styles.emptyBush, styles.emptyBushRight]} />
            </View>
            <Text style={styles.emptyTitle}>
              {filtering ? 'No reports match this filter' : 'No live reports right now'}
            </Text>
            <Text style={styles.emptySubtitle}>
              {filtering
                ? 'Try clearing the filter or search to see more.'
                : 'Be the first to post one and help others stay informed.'}
            </Text>
            <Pressable
              style={styles.emptyCta}
              onPress={() => {
                if (!gate()) return;
                setFormDistrict(districtKey);
                setComposing(true);
              }}
            >
              <Ionicons name="sparkles-outline" size={16} color={Palette.onDark} />
              <Text style={styles.emptyCtaText}>Post a report</Text>
            </Pressable>
          </View>
        ) : (
          reports.map((r) => (
            <View key={r.id} style={styles.log}>
              <View style={styles.logHead}>
                <View style={styles.logAvatar}>
                  {r.authorAvatar ? (
                    <Image source={{ uri: r.authorAvatar }} style={styles.logAvatarImg} />
                  ) : (
                    <Text style={styles.logAvatarText}>
                      {(r.author || '?').slice(0, 1).toUpperCase()}
                    </Text>
                  )}
                </View>
                <Text style={styles.logTitle}>{r.title}</Text>
                <Text style={styles.logAgo}>{ago(r.at)}</Text>
                {user && r.author === user.username ? (
                  <Pressable
                    onPress={() => removeReport(r.id)}
                    disabled={deletingId === r.id}
                    hitSlop={8}
                    style={styles.logDelete}
                    accessibilityLabel={`Delete report: ${r.title}`}
                  >
                    {deletingId === r.id ? (
                      <ActivityIndicator size={12} color={Palette.danger} />
                    ) : (
                      <Ionicons name="trash-outline" size={15} color={Palette.danger} />
                    )}
                  </Pressable>
                ) : null}
              </View>
              {r.body ? <Text style={styles.logBody}>{r.body}</Text> : null}
              <View style={styles.logMeta}>
                <Ionicons name="location-outline" size={11} color={Palette.textDim} />
                <Text style={styles.logDistrict}>
                  {r.location} · {r.districtName}
                  {r.author ? ` · by @${r.author}` : ''}
                </Text>
                <View style={styles.logPosted}>
                  <Ionicons name="time-outline" size={11} color={Palette.textDim} />
                  <Text style={styles.logDistrict}>Posted {postedAt(r.at)}</Text>
                </View>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      <DistrictSheet
        visible={sheetTarget !== null}
        title={sheetTarget === 'filter' ? 'Filter by district' : 'Report from which district?'}
        onClose={() => setSheetTarget(null)}
        onSelect={(key) => {
          if (sheetTarget === 'filter') setFilterKey(key);
          if (sheetTarget === 'form') setFormDistrict(key);
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  content: { padding: Space.lg, paddingBottom: Space.section },
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    padding: Space.lg,
    borderRadius: Radius.lg,
    backgroundColor: Palette.primaryTint,
  },
  triggerIcon: {
    width: 40,
    height: 40,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  triggerBody: { flex: 1 },
  triggerText: {
    ...Type.label,
    fontSize: 15,
    color: Palette.text,
  },
  triggerMeta: {
    ...Type.body,
    fontSize: 12,
    lineHeight: 16,
    color: Palette.textMuted,
    marginTop: 2,
  },
  triggerGo: {
    width: 34,
    height: 34,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryDeep,
    alignItems: 'center',
    justifyContent: 'center',
  },
  form: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
    gap: Space.sm,
  },
  fieldLabel: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
  },
  formDistrict: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Palette.canvas,
    borderRadius: Radius.sm,
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
  },
  formDistrictBody: { flex: 1 },
  formDistrictValue: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
  },
  input: {
    backgroundColor: Palette.canvas,
    borderRadius: Radius.sm,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
    ...Type.body,
    color: Palette.text,
  },
  shareLocation: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    paddingVertical: 4,
  },
  shareLocationText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
  },
  shareLocationHint: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
    marginTop: -2,
  },
  locationError: {
    ...Type.caption,
    fontSize: 11,
    color: Palette.danger,
  },
  multiline: {
    height: 76,
    textAlignVertical: 'top',
  },
  formActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: Space.sm,
  },
  cancel: {
    paddingHorizontal: Space.lg,
    paddingVertical: Space.sm,
  },
  cancelText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.textMuted,
  },
  submit: {
    paddingHorizontal: Space.lg,
    paddingVertical: Space.sm,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primary,
    minWidth: 96,
    alignItems: 'center',
  },
  submitOff: { opacity: 0.5 },
  submitText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.onDark,
  },
  filterWrap: {
    marginTop: Space.lg,
  },
  clear: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    marginTop: Space.sm,
    paddingVertical: 4,
  },
  clearText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.danger,
  },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    marginTop: Space.sm,
    marginBottom: Space.md,
  },
  searchInput: {
    flex: 1,
    height: 40,
    ...Type.body,
    color: Palette.text,
  },
  loading: {
    padding: Space.xl,
    alignItems: 'center',
  },
  emptyCard: {
    alignItems: 'center',
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    paddingVertical: Space.section,
    paddingHorizontal: Space.xl,
  },
  emptyCircle: {
    width: 128,
    height: 128,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'flex-end',
    overflow: 'hidden',
    marginBottom: Space.lg,
  },
  emptyPost: {
    position: 'absolute',
    bottom: 28,
    width: 4,
    height: 56,
    borderRadius: 2,
    backgroundColor: Palette.primary,
    opacity: 0.55,
  },
  emptySign: {
    position: 'absolute',
    bottom: 62,
    width: 50,
    height: 16,
    borderRadius: 3,
    backgroundColor: Palette.primary,
    opacity: 0.6,
  },
  emptyBush: {
    position: 'absolute',
    bottom: 16,
    width: 34,
    height: 34,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primary,
    opacity: 0.35,
  },
  emptyBushLeft: { left: 24 },
  emptyBushRight: { right: 24 },
  emptyTitle: {
    ...Type.label,
    fontSize: 17,
    color: Palette.text,
  },
  emptySubtitle: {
    ...Type.body,
    fontSize: 13,
    color: Palette.textMuted,
    textAlign: 'center',
    marginTop: Space.sm,
    maxWidth: 240,
  },
  emptyCta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginTop: Space.lg,
    paddingHorizontal: Space.xl,
    paddingVertical: Space.md,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryDeep,
  },
  emptyCtaText: {
    ...Type.label,
    color: Palette.onDark,
  },
  log: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
    marginBottom: Space.sm,
  },
  logHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.sm,
  },
  logAvatar: {
    width: 26,
    height: 26,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  logAvatarImg: {
    width: 26,
    height: 26,
    borderRadius: Radius.pill,
  },
  logAvatarText: {
    ...Type.label,
    fontSize: 11,
    color: Palette.primaryDeep,
  },
  logTitle: {
    ...Type.label,
    color: Palette.text,
    flex: 1,
  },
  logAgo: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
  logDelete: {
    marginLeft: Space.xs,
    padding: 2,
  },
  logBody: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 4,
  },
  logMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginTop: Space.sm,
  },
  logPosted: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginLeft: 'auto',
  },
  logDistrict: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
  },
});
