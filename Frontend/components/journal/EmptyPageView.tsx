/**
 * EmptyPageView — a blank leaf. The next unwritten page invites the
 * traveller to fill it; pages further ahead are just blank paper (you
 * can't skip ahead — one page per location, in order).
 */
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { JournalFont, JournalPalette } from './JournalTheme';

export function EmptyPageView({
  pageNumber,
  writable,
  onPress,
}: {
  pageNumber: number;
  writable: boolean;
  onPress?: () => void;
}) {
  return (
    <View style={styles.leaf}>
      <View style={styles.center}>
        <Ionicons
          name={writable ? 'create-outline' : 'book-outline'}
          size={30}
          color={writable ? JournalPalette.wax : JournalPalette.parchmentEdge}
        />
        {writable ? (
          <>
            <Text style={styles.title}>This page is blank…</Text>
            <Pressable style={styles.cta} onPress={onPress}>
              <Text style={styles.ctaText}>Write here</Text>
            </Pressable>
          </>
        ) : (
          <Text style={styles.lockedText}>Fill the page before this one first</Text>
        )}
      </View>
      <Text style={styles.stampText}>Page {pageNumber}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  leaf: {
    flex: 1,
    backgroundColor: JournalPalette.parchment,
    borderRadius: 6,
    padding: 22,
    justifyContent: 'space-between',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  title: {
    fontFamily: JournalFont.hand,
    fontSize: 22,
    color: JournalPalette.inkFaded,
  },
  lockedText: {
    fontFamily: JournalFont.hand,
    fontSize: 18,
    color: JournalPalette.parchmentEdge,
    textAlign: 'center',
    maxWidth: 200,
  },
  cta: {
    marginTop: 4,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: JournalPalette.wax,
  },
  ctaText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 14,
    color: JournalPalette.wax,
  },
  stampText: {
    alignSelf: 'flex-end',
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.parchmentEdge,
  },
});
