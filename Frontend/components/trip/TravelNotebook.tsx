import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { TravelNote, deleteTravelNote, fetchTravelNotes } from '../../lib/api';
import { districts } from '../../constants/districts';
import { districtHero } from '../../constants/district-hero';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

const noteDate = (at: number) =>
  new Date(at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

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
  }, []);

  const remove = async (id: string) => {
    const next = notes.filter((x) => x.id !== id);
    setNotes(next);
    onNotesChange?.(next);
    try {
      await deleteTravelNote(id);
    } catch {
      load();
    }
  };

  const shown = typeof limit === 'number' ? notes.slice(0, limit) : notes;

  return (
    <View>
      <Pressable style={styles.trigger} onPress={() => router.push('/journal')}>
        <View style={styles.triggerIcon}>
          <Ionicons name="create-outline" size={17} color={Palette.primaryDeep} />
        </View>
        <View style={styles.triggerBody}>
          <Text style={styles.triggerTitle}>Write a travel note</Text>
          <Text style={styles.triggerSubtitle}>Capture your experiences and memories.</Text>
        </View>
        <Ionicons name="chevron-forward" size={16} color={Palette.primaryDeep} />
      </Pressable>

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
