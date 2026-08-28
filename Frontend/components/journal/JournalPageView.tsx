import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { JournalFont, JournalPalette } from './JournalTheme';
import { JournalPage } from '../../lib/api';

const tiltFor = (seed: number) => ((seed * 37) % 7) - 3;

export function JournalPageView({
  page,
  onDelete,
}: {
  page: JournalPage;
  onDelete?: () => void;
}) {
  return (
    <View style={styles.leaf}>
      <VignetteEdges />

      {onDelete ? (
        <Pressable style={styles.trash} onPress={onDelete} hitSlop={10}>
          <Ionicons name="trash-outline" size={16} color={JournalPalette.inkFaded} />
        </Pressable>
      ) : null}

      <View style={styles.headRow}>
        <Ionicons name="location" size={16} color={JournalPalette.wax} />
        <Text style={styles.place} numberOfLines={2}>
          {page.place}
        </Text>
      </View>
      <View style={styles.rule} />

      <Text style={styles.body}>{page.body}</Text>

      {page.photoUrl ? (
        <View style={[styles.photoWrap, { transform: [{ rotate: `${tiltFor(page.pageNumber)}deg` }] }]}>
          <Image source={{ uri: page.photoUrl }} style={styles.photo} resizeMode="cover" />
          <LinearGradient
            colors={['rgba(120, 84, 40, 0.16)', 'rgba(120, 84, 40, 0.03)']}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.tape, styles.tapeLeft]} />
          <View style={[styles.tape, styles.tapeRight]} />
        </View>
      ) : null}

      <View style={styles.stamp}>
        <Text style={styles.stampText}>Page {page.pageNumber}</Text>
      </View>
    </View>
  );
}

/** Four thin edge gradients, faked as a "vignette" — RN has no radial gradient. */
function VignetteEdges() {
  return (
    <>
      <LinearGradient
        colors={[JournalPalette.vignette, 'transparent']}
        style={[styles.edge, { top: 0, height: 40 }]}
      />
      <LinearGradient
        colors={['transparent', JournalPalette.vignette]}
        style={[styles.edge, { bottom: 0, height: 40 }]}
      />
      <LinearGradient
        colors={[JournalPalette.vignette, 'transparent']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[styles.edgeV, { left: 0, width: 24 }]}
      />
      <LinearGradient
        colors={['transparent', JournalPalette.vignette]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[styles.edgeV, { right: 0, width: 24 }]}
      />
    </>
  );
}

const styles = StyleSheet.create({
  leaf: {
    flex: 1,
    backgroundColor: JournalPalette.parchment,
    borderRadius: 6,
    padding: 22,
    paddingTop: 26,
    overflow: 'hidden',
  },
  edge: { position: 'absolute', left: 0, right: 0 },
  edgeV: { position: 'absolute', top: 0, bottom: 0 },
  trash: {
    position: 'absolute',
    top: 14,
    right: 14,
    zIndex: 3,
    padding: 4,
  },
  headRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingRight: 28,
  },
  place: {
    flex: 1,
    fontFamily: JournalFont.serifBold,
    fontSize: 24,
    color: JournalPalette.ink,
  },
  rule: {
    height: 1,
    borderBottomWidth: 1,
    borderStyle: 'dashed',
    borderColor: JournalPalette.parchmentEdge,
    marginTop: 8,
    marginBottom: 14,
  },
  body: {
    fontFamily: JournalFont.hand,
    fontSize: 22,
    lineHeight: 27,
    color: JournalPalette.ink,
  },
  photoWrap: {
    alignSelf: 'center',
    marginTop: 18,
    width: 168,
    height: 168,
    backgroundColor: JournalPalette.photoBorder,
    padding: 8,
    paddingBottom: 22,
    borderRadius: 2,
    shadowColor: '#000',
    shadowOpacity: 0.35,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 5 },
    elevation: 6,
  },
  photo: {
    width: '100%',
    height: '100%',
    borderRadius: 1,
  },
  tape: {
    position: 'absolute',
    width: 46,
    height: 20,
    top: -8,
    backgroundColor: JournalPalette.tape,
    borderWidth: 1,
    borderColor: 'rgba(180, 150, 100, 0.4)',
  },
  tapeLeft: { left: -6, transform: [{ rotate: '-12deg' }] },
  tapeRight: { right: -6, transform: [{ rotate: '10deg' }] },
  stamp: {
    position: 'absolute',
    bottom: 14,
    right: 18,
  },
  stampText: {
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.inkFaded,
    letterSpacing: 0.4,
  },
});
