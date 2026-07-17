import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { DistrictSheet } from '../components/trip/DistrictSheet';
import { Empty, ScreenTitle } from '../components/trip/Ui';
import { useTrip } from '../lib/store';
import { useAuthGate } from '../lib/auth';
import { districtByKey } from '../constants/districts';
import { GroundReport, fetchGroundReports, postGroundReport } from '../lib/api';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

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

  const [reports, setReports] = useState<GroundReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

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

  const submit = async () => {
    if (!location.trim() || !title.trim()) return;
    if (!gate()) return; // token may have expired since the form opened
    setPosting(true);
    try {
      await postGroundReport({
        districtKey: formDistrict,
        location: location.trim(),
        title: title.trim(),
        body: body.trim(),
      });
      setLocation('');
      setTitle('');
      setBody('');
      setComposing(false);
      await load(filterKey, search);
    } catch {
      setFailed(true);
    } finally {
      setPosting(false);
    }
  };

  const filterDistrict = filterKey ? districtByKey(filterKey) : null;
  const filtering = filterKey !== null || search.trim() !== '';

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <ScreenTitle
          title="Ground Reports"
          subtitle="Live conditions from travellers on the ground. Every report expires after 24 hours."
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
              <Pressable onPress={() => setComposing(false)} style={styles.cancel}>
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
            <Ionicons name="add-circle-outline" size={17} color={Palette.primary} />
            <Text style={styles.triggerText}>Report ground conditions here</Text>
          </Pressable>
        )}

        {/* filter + clear + search */}
        <View style={styles.filterRow}>
          <Pressable style={styles.filterChip} onPress={() => setSheetTarget('filter')}>
            <Ionicons name="funnel-outline" size={13} color={Palette.primary} />
            <Text style={styles.filterChipText}>
              {filterDistrict ? filterDistrict.name : 'All districts'}
            </Text>
            <Ionicons name="chevron-down" size={12} color={Palette.textMuted} />
          </Pressable>

          {filtering ? (
            <Pressable
              style={styles.clear}
              onPress={() => {
                setFilterKey(null);
                setSearch('');
              }}
            >
              <Ionicons name="close-circle" size={14} color={Palette.danger} />
              <Text style={styles.clearText}>Clear</Text>
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
        {loading ? (
          <View style={styles.loading}>
            <ActivityIndicator color={Palette.primary} />
          </View>
        ) : failed ? (
          <Empty text="Can't reach the server. Ground reports need a connection." />
        ) : reports.length === 0 ? (
          <Empty
            text={
              filtering
                ? 'No live reports match this filter. Try clearing it.'
                : 'No live reports right now. Be the first to post one.'
            }
          />
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
    gap: Space.sm,
    padding: Space.md,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Palette.primary,
    backgroundColor: Palette.primaryTint,
  },
  triggerText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primaryDeep,
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
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginTop: Space.lg,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.pill,
    paddingHorizontal: Space.md,
    paddingVertical: 7,
  },
  filterChipText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
  },
  clear: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Space.sm,
    paddingVertical: 7,
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
