/**
 * app/journal.tsx — the pirate travel journal: a book of up to
 * MAX_PAGES_PER_BOOK pages, one location per page, photos glued in. Reached
 * from Profile's "Write a travel note" card; not a tab, so it has its own
 * back button rather than living in the bottom bar.
 *
 * The page-flip is built on React Native's own Animated API (transform +
 * opacity only, so it runs on the native driver) — no reanimated/worklets,
 * which keeps this screen out of the native-build/NDK cost the rest of the
 * app deliberately avoids (see components/trip/DistrictMap.tsx).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { EmptyPageView } from '../components/journal/EmptyPageView';
import { JournalPageView } from '../components/journal/JournalPageView';
import { PageTabs } from '../components/journal/PageTabs';
import { WriteForm } from '../components/journal/WriteForm';
import { JournalFont, JournalPalette, MAX_PAGES_PER_BOOK } from '../components/journal/JournalTheme';
import { useAuth } from '../lib/auth';
import {
  JournalBook,
  JournalDetail,
  createJournal,
  createJournalPage,
  deleteJournalPage,
  fetchJournal,
  fetchJournals,
} from '../lib/api';

export default function JournalScreen() {
  const { user } = useAuth();
  const [books, setBooks] = useState<JournalBook[]>([]);
  const [bookIndex, setBookIndex] = useState(0);
  const [detail, setDetail] = useState<JournalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [renderedPage, setRenderedPage] = useState(1);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [writing, setWriting] = useState(false);
  const flip = useRef(new Animated.Value(1)).current;

  const activeBook = books[bookIndex] ?? null;

  const loadBooks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchJournals();
      setBooks(list);
      setBookIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your journal.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadBooks();
  }, [user, loadBooks]);

  const loadDetail = useCallback(async (bookId: string, landOnPage?: number) => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchJournal(bookId);
      setDetail(d);
      setRenderedPage(landOnPage ?? Math.max(1, Math.min(d.pageCount + 1, MAX_PAGES_PER_BOOK)));
      flip.setValue(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open this book.');
    } finally {
      setLoading(false);
    }
  }, [flip]);

  useEffect(() => {
    if (activeBook) loadDetail(activeBook.id);
    else setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBook?.id]);

  const goToPage = (target: number) => {
    if (writing || target === renderedPage || target < 1 || target > MAX_PAGES_PER_BOOK) return;
    setDirection(target > renderedPage ? 1 : -1);
    Animated.timing(flip, { toValue: 0, duration: 170, useNativeDriver: true }).start(() => {
      setRenderedPage(target);
      Animated.timing(flip, { toValue: 1, duration: 220, useNativeDriver: true }).start();
    });
  };

  const startNewBook = async () => {
    setBusy(true);
    try {
      const book = await createJournal();
      setBooks((prev) => [book, ...prev]);
      setBookIndex(0);
    } catch (e) {
      Alert.alert('Could not start a new book', e instanceof Error ? e.message : 'Try again.');
    } finally {
      setBusy(false);
    }
  };

  const savePage = async (entry: { place: string; body: string; photoUrl: string }) => {
    if (!activeBook) return;
    const created = await createJournalPage(activeBook.id, entry);
    setBooks((prev) =>
      prev.map((b) => (b.id === activeBook.id ? { ...b, pageCount: b.pageCount + 1 } : b)),
    );
    setWriting(false);
    await loadDetail(activeBook.id, created.pageNumber);
  };

  const deletePage = (pageId: string, pageNumber: number) => {
    if (!activeBook) return;
    Alert.alert('Tear out this page?', 'This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteJournalPage(activeBook.id, pageId);
            setBooks((prev) =>
              prev.map((b) => (b.id === activeBook.id ? { ...b, pageCount: b.pageCount - 1 } : b)),
            );
            await loadDetail(activeBook.id, Math.max(1, Math.min(pageNumber, MAX_PAGES_PER_BOOK)));
          } catch (e) {
            Alert.alert('Could not delete the page', e instanceof Error ? e.message : 'Try again.');
          }
        },
      },
    ]);
  };

  const filledCount = detail?.pageCount ?? 0;
  const pageData = detail?.pages.find((p) => p.pageNumber === renderedPage) ?? null;
  const isNextBlank = renderedPage === filledCount + 1 && filledCount < MAX_PAGES_PER_BOOK;
  const bookFull = filledCount >= MAX_PAGES_PER_BOOK;

  const flipStyle = {
    opacity: flip,
    transform: [
      { translateX: flip.interpolate({ inputRange: [0, 1], outputRange: [direction * 50, 0] }) },
      { scaleX: flip.interpolate({ inputRange: [0, 1], outputRange: [0.86, 1] }) },
    ],
  };

  return (
    <View style={styles.leather}>
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <Pressable
            style={styles.headerBtn}
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/profile'))}
            hitSlop={8}
          >
            <Ionicons name="arrow-back" size={20} color={JournalPalette.goldBright} />
          </Pressable>

          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle} numberOfLines={1}>
              {activeBook?.title ?? 'Travel Journal'}
            </Text>
            {books.length > 1 ? (
              <Text style={styles.headerSub}>Book {bookIndex + 1} of {books.length}</Text>
            ) : null}
          </View>

          <View style={styles.headerRight}>
            {books.length > 1 ? (
              <>
                <Pressable
                  style={styles.headerBtn}
                  onPress={() => setBookIndex((i) => Math.min(i + 1, books.length - 1))}
                  disabled={bookIndex >= books.length - 1}
                  hitSlop={8}
                >
                  <Ionicons
                    name="chevron-back"
                    size={18}
                    color={bookIndex >= books.length - 1 ? JournalPalette.gold : JournalPalette.goldBright}
                  />
                </Pressable>
                <Pressable
                  style={styles.headerBtn}
                  onPress={() => setBookIndex((i) => Math.max(i - 1, 0))}
                  disabled={bookIndex <= 0}
                  hitSlop={8}
                >
                  <Ionicons
                    name="chevron-forward"
                    size={18}
                    color={bookIndex <= 0 ? JournalPalette.gold : JournalPalette.goldBright}
                  />
                </Pressable>
              </>
            ) : null}
            <Pressable style={styles.headerBtn} onPress={startNewBook} disabled={busy} hitSlop={8}>
              <Ionicons name="add-circle-outline" size={20} color={JournalPalette.goldBright} />
            </Pressable>
          </View>
        </View>

        {!user ? (
          <View style={styles.center}>
            <Ionicons name="lock-closed-outline" size={26} color={JournalPalette.goldBright} />
            <Text style={styles.centerText}>Log in to keep a travel journal.</Text>
          </View>
        ) : loading && !detail ? (
          <View style={styles.center}>
            <ActivityIndicator color={JournalPalette.goldBright} />
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.centerText}>{error}</Text>
          </View>
        ) : !activeBook ? (
          <View style={styles.center}>
            <Ionicons name="book-outline" size={40} color={JournalPalette.goldBright} />
            <Text style={styles.centerTitle}>Your journal is empty</Text>
            <Text style={styles.centerText}>Start your first book and write your first page.</Text>
            <Pressable style={styles.newBookCta} onPress={startNewBook} disabled={busy}>
              {busy ? (
                <ActivityIndicator color={JournalPalette.leatherDeep} />
              ) : (
                <Text style={styles.newBookCtaText}>Start Book 1</Text>
              )}
            </Pressable>
          </View>
        ) : (
          <View style={styles.bookArea}>
            <View style={styles.pageStage}>
              <Animated.View style={[styles.pageSlot, flipStyle]}>
                {writing ? (
                  <WriteForm onCancel={() => setWriting(false)} onSave={savePage} />
                ) : pageData ? (
                  <JournalPageView
                    page={pageData}
                    onDelete={() => deletePage(pageData.id, pageData.pageNumber)}
                  />
                ) : (
                  <EmptyPageView
                    pageNumber={renderedPage}
                    writable={isNextBlank}
                    onPress={() => setWriting(true)}
                  />
                )}
              </Animated.View>
            </View>

            <PageTabs filledCount={filledCount} current={renderedPage} onSelect={goToPage} />
          </View>
        )}

        {activeBook && !writing ? (
          <View style={styles.navRow}>
            <Pressable
              style={[styles.navBtn, renderedPage <= 1 && styles.navBtnOff]}
              onPress={() => goToPage(renderedPage - 1)}
              disabled={renderedPage <= 1}
            >
              <Ionicons name="chevron-back" size={16} color={JournalPalette.parchment} />
              <Text style={styles.navText}>Prev</Text>
            </Pressable>
            <Text style={styles.navCount}>
              {renderedPage} / {MAX_PAGES_PER_BOOK}
            </Text>
            <Pressable
              style={[styles.navBtn, renderedPage >= MAX_PAGES_PER_BOOK && styles.navBtnOff]}
              onPress={() => goToPage(renderedPage + 1)}
              disabled={renderedPage >= MAX_PAGES_PER_BOOK || renderedPage > filledCount}
            >
              <Text style={styles.navText}>Next</Text>
              <Ionicons name="chevron-forward" size={16} color={JournalPalette.parchment} />
            </Pressable>
          </View>
        ) : null}

        {bookFull && !writing ? (
          <View style={styles.fullBanner}>
            <Text style={styles.fullBannerText}>This book is full — start a new one to keep writing.</Text>
            <Pressable style={styles.fullBannerCta} onPress={startNewBook} disabled={busy}>
              <Text style={styles.fullBannerCtaText}>New book</Text>
            </Pressable>
          </View>
        ) : null}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  leather: {
    flex: 1,
    backgroundColor: JournalPalette.leatherDeep,
  },
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  headerBtn: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerTitle: {
    fontFamily: JournalFont.serifBold,
    fontSize: 18,
    color: JournalPalette.goldBright,
  },
  headerSub: {
    fontFamily: JournalFont.serif,
    fontSize: 11,
    color: JournalPalette.gold,
    marginTop: 1,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 32,
  },
  centerTitle: {
    fontFamily: JournalFont.serifBold,
    fontSize: 20,
    color: JournalPalette.goldBright,
  },
  centerText: {
    fontFamily: JournalFont.serif,
    fontSize: 13,
    color: JournalPalette.gold,
    textAlign: 'center',
  },
  newBookCta: {
    marginTop: 8,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
    backgroundColor: JournalPalette.goldBright,
    minWidth: 140,
    alignItems: 'center',
  },
  newBookCtaText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 14,
    color: JournalPalette.leatherDeep,
  },
  bookArea: {
    flex: 1,
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingBottom: 8,
    gap: 4,
  },
  pageStage: {
    flex: 1,
    borderRadius: 8,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  pageSlot: {
    flex: 1,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  navBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  navBtnOff: {
    opacity: 0.3,
  },
  navText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 13,
    color: JournalPalette.parchment,
  },
  navCount: {
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.gold,
  },
  fullBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 14,
    marginBottom: 12,
    padding: 12,
    borderRadius: 10,
    backgroundColor: 'rgba(217, 172, 92, 0.15)',
    borderWidth: 1,
    borderColor: JournalPalette.gold,
  },
  fullBannerText: {
    flex: 1,
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.goldBright,
    marginRight: 10,
  },
  fullBannerCta: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
    backgroundColor: JournalPalette.goldBright,
  },
  fullBannerCtaText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 12,
    color: JournalPalette.leatherDeep,
  },
});
