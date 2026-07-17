/**
 * TravelNotebook — the logged-in traveller's private journal: where they
 * went, what they saw. Entries live on the server until deleted.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
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
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const noteDate = (at: number) =>
  new Date(at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

export function TravelNotebook() {
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
      setNotes(await fetchTravelNotes());
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
    setNotes((n) => n.filter((x) => x.id !== id)); // optimistic
    try {
      await deleteTravelNote(id);
    } catch {
      load(); // restore truth on failure
    }
  };

  return (
    <View style={styles.card}>
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
          <Ionicons name="create-outline" size={16} color={Palette.primary} />
          <Text style={styles.triggerText}>Write a travel note</Text>
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
        notes.map((n) => (
          <View key={n.id} style={styles.note}>
            <View style={styles.noteHead}>
              <Ionicons name="location" size={12} color={Palette.primary} />
              <Text style={styles.notePlace}>{n.place}</Text>
              <Text style={styles.noteDate}>{noteDate(n.at)}</Text>
              <Pressable onPress={() => remove(n.id)} hitSlop={8}>
                <Ionicons name="trash-outline" size={14} color={Palette.textDim} />
              </Pressable>
            </View>
            <Text style={styles.noteBody}>{n.body}</Text>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.md,
  },
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
    gap: Space.sm,
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
  },
  note: {
    marginTop: Space.sm,
    padding: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.canvas,
  },
  noteHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  notePlace: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
    flex: 1,
  },
  noteDate: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
  },
  noteBody: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    lineHeight: 17,
    marginTop: 4,
  },
});
