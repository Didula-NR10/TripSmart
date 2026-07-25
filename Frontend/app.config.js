// Dynamic Expo config. Loads on top of app.json.
// No Google Maps key needed — the map picker runs on free OpenStreetMap
// tiles (Leaflet) on every platform, see components/trip/DistrictMap.
export default ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    package: 'com.didulanr.tripsmart',
  },
  // Append, never replace — app.json already declares expo-router and expo-splash-screen.
  plugins: [...(config.plugins ?? []), 'expo-font'],
});