/**
 * JournalTheme — the pirate/travel-journal palette and type scale. Deliberately
 * separate from constants/trip-theme (the app's teal design system): this
 * screen is meant to feel like a different physical object — an old leather
 * diary — not another app screen, so it gets its own aged-paper colors and
 * handwriting/serif fonts (Caveat, Playfair Display; loaded in app/_layout.tsx).
 */
export const JournalPalette = {
  parchment: '#F1E2BE',
  parchmentDeep: '#E4CE9C',
  parchmentEdge: '#C9A96B',
  vignette: 'rgba(94, 62, 25, 0.28)',

  ink: '#3B2A18',
  inkFaded: '#6B5636',

  leather: '#5C3A21',
  leatherDeep: '#3E2714',
  gold: '#B8863B',
  goldBright: '#D9AC5C',

  tape: 'rgba(230, 214, 176, 0.75)',
  photoBorder: '#FAF6EC',

  wax: '#7A2E22',
  danger: '#8C2F20',
} as const;

export const JournalFont = {
  hand: 'Caveat_400Regular',
  handBold: 'Caveat_700Bold',
  serif: 'PlayfairDisplay_600SemiBold',
  serifBold: 'PlayfairDisplay_700Bold',
} as const;

export const MAX_PAGES_PER_BOOK = 10;
