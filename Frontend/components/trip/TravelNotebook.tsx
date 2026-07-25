/**
 * TravelNotebook — the logged-in traveller's private journal: where they
 * went, what they saw. Entries live on the server until deleted.
 *
 * `limit` caps how many notes are shown (the Profile screen passes 2 by
 * default and lets "View all" lift the cap). `onNotesChange` reports the
 * full, unfiltered list up to the parent so it can derive the travel-summary
 * stats without a second fetch.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  TravelNote,
  deleteTravelNote,
  fetchTravelNotes,
  postTravelNote,
} from '../../lib/api';
import { districts } from '../../constants/districts';
import { districtHero } from '../../constants/district-hero';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const noteDate = (at: number) =>
  new Date(at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

/** Best-effort landmark photo for a note, matched from its free-text place
 *  field against the same district/landmark data the Forecast tab uses. */
function thumbnailFor(place: string): string | null {
  const p = place.toLowerCase();
  for (const d of districts) {
    const hero = districtHero[d.key];
    if (!hero) continue;
    const words = [d.name, ...hero.landmark.split(/[\s,]+/)]
      .map((w) => w.toLowerCase())
      .filter((w) => w.length >= 4);
    if (words.some((w) => p.includes(w))) return hero.url;
  }
  return null;
}

export function TravelNotebook({
  limit,
  onNotesChange,
}: {
  limit?: number;
  onNotesChange?: (notes: TravelNote[]) => void;
}) {
  const [notes, setNotes] = useState<TravelNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const [composing, setComposing] = useState(false);
  const [place, setPlace] = useState('');
  const [body, setBody] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await fetchTravelNotes();
      setNotes(fresh);
      onNotesChange?.(fresh);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [onNotesChange]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!place.trim() || !body.trim()) return;
    setSaving(true);
    try {
      await postTravelNote({ place: place.trim(), body: body.trim() });
      setPlace('');
      setBody('');
      setComposing(false);
      await load();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    const next = notes.filter((x) => x.id !== id);
    setNotes(next); // optimistic
    onNotesChange?.(next);
    try {
      await deleteTravelNote(id);
    } catch {
      load(); // restore truth on failure
    }
  };

  const shown = typeof limit === 'number' ? notes.slice(0, limit) : notes;

  return (
    <View>
      {composing ? (
        <View style={styles.form}>
          <TextInput
            value={place}
            onChangeText={setPlace}
            placeholder="Where did you go? e.g. Sigiriya, Ella Rock"
            placeholderTextColor={Palette.textDim}
            style={styles.input}
          />
          <TextInput
            value={body}
            onChangeText={setBody}
            placeholder="What did you see? The view, the food, the people…"
            placeholderTextColor={Palette.textDim}
            multiline
            style={[styles.input, styles.multiline]}
          />
          <View style={styles.formActions}>
            <Pressable onPress={() => setComposing(false)} style={styles.cancel}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable
              onPress={save}
              disabled={saving || !place.trim() || !body.trim()}
              style={[
                styles.save,
                (saving || !place.trim() || !body.trim()) && styles.saveOff,
              ]}
            >
              {saving ? (
                <ActivityIndicator size="small" color={Palette.onDark} />
              ) : (
                <Text style={styles.saveText}>Save note</Text>
              )}
            </Pressable>
          </View>
        </View>
      ) : (
        <Pressable style={styles.trigger} onPress={() => setComposing(true)}>
          <View style={styles.triggerIcon}>
            <Ionicons name="create-outline" size={17} color={Palette.primaryDeep} />
          </View>
          <View style={styles.triggerBody}>
            <Text style={styles.triggerTitle}>Write a travel note</Text>
            <Text style={styles.triggerSubtitle}>Capture your experiences and memories.</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={Palette.primaryDeep} />
        </Pressable>
      )}

      {loading ? (
        <View style={styles.loading}>
          <ActivityIndicator color={Palette.primary} />
        </View>
      ) : failed ? (
        <Text style={styles.empty}>Could not load your notebook. Check the backend.</Text>
      ) : notes.length === 0 ? (
        <Text style={styles.empty}>
          Nothing here yet. Note down where you went and what you saw — it stays private to
          your account.
        </Text>
      ) : (
        shown.map((n) => {
          const thumb = thumbnailFor(n.place);
          return (
            <View key={n.id} style={styles.note}>
              {thumb ? (
                <Image source={{ uri: thumb }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, styles.thumbFallback]}>
                  <Ionicons name="image-outline" size={18} color={Palette.primary} />
                </View>
              )}
              <View style={styles.noteBody}>
                <View style={styles.noteHead}>
                  <Ionicons name="location" size={12} color={Palette.primary} style={{ marginTop: 1 }} />
                  <Text style={styles.notePlace} numberOfLines={2}>
                    {n.place}
                  </Text>
                </View>
                <Text style={styles.noteText} numberOfLines={2}>
                  {n.body}
                </Text>
              </View>
              <View style={styles.noteMeta}>
                <Text style={styles.noteDate}>{noteDate(n.at)}</Text>
                <Pressable onPress={() => remove(n.id)} hitSlop={8}>
                  <Ionicons name="trash-outline" size={14} color={Palette.textDim} />
                </Pressable>
              </View>
            </View>
          );
        })
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    padding: Space.md,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Palette.primary,
    backgroundColor: Palette.primaryTint,
  },
  triggerIcon: {
    width: 32,
    height: 32,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  triggerBody: { flex: 1 },
  triggerTitle: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
  },
  triggerSubtitle: {
    ...Type.caption,
    fontSize: 10.5,
    color: Palette.textMuted,
    marginTop: 1,
  },
  form: {
    gap: Space.sm,
    backgroundColor: Palette.surface,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
  },
  input: {
    backgroundColor: Palette.canvas,
    borderRadius: Radius.sm,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
    ...Type.body,
    fontSize: 13,
    color: Palette.text,
  },
  multiline: {
    height: 84,
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
  save: {
    paddingHorizontal: Space.lg,
    paddingVertical: Space.sm,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primary,
    minWidth: 92,
    alignItems: 'center',
  },
  saveOff: { opacity: 0.5 },
  saveText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.onDark,
  },
  loading: {
    padding: Space.lg,
    alignItems: 'center',
  },
  empty: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    lineHeight: 17,
    padding: Space.md,
    marginTop: Space.sm,
  },
  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Space.md,
    marginTop: Space.md,
    padding: Space.md,
    borderRadius: Radius.lg,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
  },
  noteMeta: {
    alignItems: 'flex-end',
    gap: Space.sm,
  },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: Radius.md,
  },
  thumbFallback: {
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  noteBody: { flex: 1 },
  noteHead: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
  },
  notePlace: {
    ...Type.label,
    fontSize: 13,
    color: Palette.text,
    flex: 1,
  },
  noteDate: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textDim,
    marginTop: 2,
  },
  noteText: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    lineHeight: 17,
    marginTop: 3,
  },
});
