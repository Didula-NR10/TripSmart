// Dynamic Expo config. Loads on top of app.json.
// The map picker (components/trip/DistrictMap) renders the Google Maps
// JavaScript API inside a WebView on every platform — same WebView-based
// architecture as before, just pointed at Google's tiles instead of
// OpenStreetMap's, so no native build / react-native-maps is required and
// it still runs in Expo Go. The key below must have the Maps JavaScript
// API and Geocoding API enabled, and billing set up, in Google Cloud
// Console, or the map will show a "for development purposes only"
// watermark / fail to load.
export default ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    package: 'com.didulanr.tripsmart',
  },
  // Append, never replace — app.json already declares expo-router and expo-splash-screen.
  plugins: [...(config.plugins ?? []), 'expo-font'],
  extra: {
    ...config.extra,
    googleMapsApiKey: 'AIzaSyAmawjj1Dow4PAFA40kuMUdEQYdxfGJkdw',
  },
});