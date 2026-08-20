/**
 * DistrictMap.tsx — real map picker for native (Android/iOS).
 *
 * Same engine as the web version (DistrictMap.web.tsx): the Google Maps
 * JavaScript API loaded inside a WebView, keyed from app.config.js
 * (extra.googleMapsApiKey). This is deliberately the JS API in a WebView
 * rather than react-native-maps, so nothing here needs a native dev build —
 * it still runs in Expo Go. The contract is the same on both platforms: the
 * user drops a pin (tap or drag) and `onPick(lat, lng)` hands the
 * coordinates to the parent, which resolves the district.
 */
import { useEffect, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import Constants from 'expo-constants';
import { Ionicons } from '@expo/vector-icons';
import { District } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

const GOOGLE_MAPS_API_KEY: string =
  (Constants.expoConfig?.extra as any)?.googleMapsApiKey ?? '';

// Self-contained Google Maps page: locked to Sri Lanka, same key and bounds
// as the web picker. Pin taps/drags post {lat, lng} back to RN.
const MAP_HTML = `<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <style>
    html, body, #map { height: 100%; margin: 0; padding: 0; background: ${Palette.primaryTint}; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    const lanka = { south: 5.7, west: 79.4, north: 10.05, east: 82.1 };
    let map, marker;

    function post(lat, lng) {
      window.ReactNativeWebView.postMessage(JSON.stringify({ lat, lng }));
    }

    function initMap() {
      map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: __LAT__, lng: __LNG__ },
        zoom: 9,
        minZoom: 7,
        restriction: { latLngBounds: lanka, strictBounds: false },
        disableDefaultUI: true,
      });
      marker = new google.maps.Marker({
        position: { lat: __LAT__, lng: __LNG__ },
        map,
        draggable: true,
      });
      marker.addListener('dragend', () => {
        const p = marker.getPosition();
        post(p.lat(), p.lng());
      });
      map.addListener('click', (e) => {
        marker.setPosition(e.latLng);
        post(e.latLng.lat(), e.latLng.lng());
      });
    }
    window.initMap = initMap;

    // Bridge for RN -> WebView recentring when the selected district changes.
    document.addEventListener('message', onRNMessage);
    window.addEventListener('message', onRNMessage);
    function onRNMessage(e) {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'recenter' && map && marker) {
          map.setCenter({ lat: msg.lat, lng: msg.lng });
          map.setZoom(9);
          marker.setPosition({ lat: msg.lat, lng: msg.lng });
        }
      } catch {}
    }
  </script>
  <script src="https://maps.googleapis.com/maps/api/js?key=__API_KEY__&callback=initMap" async></script>
</body>
</html>`;

export function DistrictMap({ selected, pin, onPick }: Props) {
  const webRef = useRef<WebView>(null);

  const html = MAP_HTML.replaceAll('__LAT__', String(selected.lat))
    .replaceAll('__LNG__', String(selected.lng))
    .replaceAll('__API_KEY__', GOOGLE_MAPS_API_KEY);

  // District chosen from the search sheet (pin cleared by the parent): recentre on it.
  useEffect(() => {
    if (pin) return;
    webRef.current?.postMessage(JSON.stringify({ type: 'recenter', lat: selected.lat, lng: selected.lng }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.key]);

  const onMessage = (e: WebViewMessageEvent) => {
    try {
      const { lat, lng } = JSON.parse(e.nativeEvent.data);
      onPick(lat, lng);
    } catch {
      // Ignore malformed bridge messages.
    }
  };

  return (
    <View style={styles.wrap}>
      <WebView
        ref={webRef}
        source={{ html }}
        onMessage={onMessage}
        style={StyleSheet.absoluteFill}
        javaScriptEnabled
        domStorageEnabled
        originWhitelist={['*']}
      />

      <View style={styles.legend}>
        <Ionicons name="location" size={13} color={Palette.primary} />
        <Text style={styles.legendText}>{selected.name}</Text>
      </View>

      <View style={styles.hint}>
        <Text style={styles.hintText}>Tap anywhere — the pin resolves to its district</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 300,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    overflow: 'hidden',
    backgroundColor: Palette.primaryTint,
  },
  legend: {
    position: 'absolute',
    bottom: Space.md,
    left: Space.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Palette.surface,
    paddingHorizontal: Space.md,
    paddingVertical: 7,
    borderRadius: Radius.pill,
  },
  legendText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
  },
  hint: {
    position: 'absolute',
    top: Space.md,
    alignSelf: 'center',
    backgroundColor: Palette.surface,
    borderRadius: Radius.pill,
    paddingHorizontal: Space.md,
    paddingVertical: 5,
  },
  hintText: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.textMuted,
  },
});
