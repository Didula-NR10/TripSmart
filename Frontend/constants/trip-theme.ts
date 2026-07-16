export const Palette = {
  canvas: '#F5F8F9',
  surface: '#FFFFFF',
  border: '#E7ECEF',
  borderSoft: '#F0F4F5',

  text: '#0F1E28',
  textMuted: '#6C7C88',
  textDim: '#98A6B0',
  onDark: '#FFFFFF',
  onDarkMuted: 'rgba(255, 255, 255, 0.82)',

  primary: '#0E7C6B',
  primaryDeep: '#0A5C50',
  primarySoft: '#D8F1EB',
  primaryTint: '#EAF7F4',

  warn: '#E0A32E',
  warnSoft: '#FBF0DA',
  danger: '#C0392B',
  dangerSoft: '#FBE4E1',
  neutralChip: '#E9EDEF',

  scrimTop: 'rgba(12, 42, 46, 0.34)',
  scrimBottom: 'rgba(9, 34, 38, 0.72)',
} as const;

export const TripFonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semi: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
} as const;

export const Type = {
  display: { fontFamily: TripFonts.bold, fontSize: 56, letterSpacing: -2.4 },
  title: { fontFamily: TripFonts.bold, fontSize: 18, letterSpacing: -0.3 },
  heading: { fontFamily: TripFonts.semi, fontSize: 16, letterSpacing: -0.2 },
  window: { fontFamily: TripFonts.bold, fontSize: 24, letterSpacing: -0.6 },
  label: { fontFamily: TripFonts.semi, fontSize: 13 },
  body: { fontFamily: TripFonts.regular, fontSize: 13, lineHeight: 19 },
  caption: { fontFamily: TripFonts.medium, fontSize: 11, letterSpacing: 0.2 },
  eyebrow: { fontFamily: TripFonts.semi, fontSize: 11, letterSpacing: 0.9 },
  tab: { fontFamily: TripFonts.medium, fontSize: 10 },
} as const;

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, section: 28 } as const;
export const Radius = { sm: 8, md: 12, lg: 16, xl: 20, xxl: 28, pill: 999 } as const;

export const Shadow = {
  card: {
    shadowColor: '#0F2A2E',
    shadowOpacity: 0.08,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 4,
  },
  soft: {
    shadowColor: '#0F2A2E',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
} as const;
