// Dynamic Expo config. Loads on top of app.json and injects secrets from .env,
// which Expo CLI reads automatically. The Maps key ships inside the APK either way —
// restrict it to this package name + SHA-1 in Google Cloud Console.
export default ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    config: {
      googleMaps: {
        apiKey: process.env.GOOGLE_MAPS_ANDROID_API_KEY ?? '',
      },
    },
  },
});
