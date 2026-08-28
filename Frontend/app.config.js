export default ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    package: 'com.didulanr.tripsmart',
  },
  plugins: [...(config.plugins ?? []), 'expo-font'],
  extra: {
    ...config.extra,
    googleMapsApiKey: 'AIzaSyAmawjj1Dow4PAFA40kuMUdEQYdxfGJkdw',
  },
});