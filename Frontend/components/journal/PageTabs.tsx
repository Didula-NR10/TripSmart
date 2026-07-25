/**
 * PageTabs — the little page-edge tabs down the side of the book (1..10).
 * Tapping one folds the book to that page. A page can only be opened if it's
 * already written, or it's the very next blank one.
 */
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { JournalFont, JournalPalette, MAX_PAGES_PER_BOOK } from './JournalTheme';

export function PageTabs({
  filledCount,
  current,
  onSelect,
}: {
  filledCount: number;
  current: number; // 1-based
  onSelect: (page: number) => void;
}) {
  return (
    <View style={styles.rail}>
      {Array.from({ length: MAX_PAGES_PER_BOOK }, (_, i) => i + 1).map((n) => {
        const reachable = n <= filledCount + 1;
        const active = n === current;
        return (
          <Pressable
            key={n}
            onPress={() => reachable && onSelect(n)}
            disabled={!reachable}
            style={[
              styles.tab,
              active && styles.tabActive,
              !reachable && styles.tabLocked,
            ]}
          >
            <Text style={[styles.tabText, active && styles.tabTextActive]}>{n}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  rail: {
    justifyContent: 'center',
    gap: 3,
  },
  tab: {
    width: 22,
    height: 22,
    borderTopLeftRadius: 3,
    borderBottomLeftRadius: 3,
    backgroundColor: JournalPalette.parchmentDeep,
    borderWidth: 1,
    borderRightWidth: 0,
    borderColor: JournalPalette.parchmentEdge,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabActive: {
    backgroundColor: JournalPalette.gold,
    width: 27,
  },
  tabLocked: {
    opacity: 0.35,
  },
  tabText: {
    fontFamily: JournalFont.serif,
    fontSize: 10,
    color: JournalPalette.ink,
  },
  tabTextActive: {
    fontFamily: JournalFont.serifBold,
    color: JournalPalette.leatherDeep,
  },
});
