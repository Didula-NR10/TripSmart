# Trip Smart UI - v6 (light travel theme, Expo SDK 54)

## 1. Dependencies

You already installed everything this needs. react-native-svg is no longer used
(this design has no line chart), so nothing new to install.

Used: expo-linear-gradient, @expo/vector-icons, @expo-google-fonts/inter,
expo-font, expo-splash-screen, expo-router, react-native-safe-area-context.

## 2. Empty the routes folder, then unzip at the project root

    Remove-Item -Recurse -Force app\*

## 3. Run

    npx expo start -c

## Files

    app/_layout.tsx          5-tab bar, mint pill on the active tab
    app/index.tsx            home
    app/explore.tsx          stub
    app/search.tsx           stub
    app/saved.tsx            stub
    app/profile.tsx          stub
    components/trip/Hero.tsx
    components/trip/BestWindowCard.tsx
    components/trip/HourlyStrip.tsx
    components/trip/DestinationGrid.tsx
    components/trip/SectionHeader.tsx
    components/trip/Placeholder.tsx
    constants/trip-theme.ts
    constants/trip-data.ts

All imports are relative. No @/ alias, so tsconfig paths cannot break this.

## Photos

Images load from remote URLs defined at the top of constants/trip-data.ts, so the
screen looks right immediately but needs a network connection on first load.

To go fully offline, drop your own photos into assets/images/ and change:

    export const heroImage = { uri: 'https://...' };

to:

    export const heroImage = require('../assets/images/kandy.jpg');

Same for each entry in `destinations`. The components already accept either form.

## Data

Everything on screen comes from constants/trip-data.ts. When the Flask GRU endpoint
is live, swap that module for a hook returning the same shapes (conditions,
bestWindow, hourly, destinations). No component changes.
