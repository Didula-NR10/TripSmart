/**
 * DistrictMap.tsx — real map picker for native (Android/iOS).
 *
 * Same engine as the web version (DistrictMap.web.tsx): Leaflet + free
 * OpenStreetMap tiles inside a WebView, so there is no Google Maps SDK, no
 * API key, and nothing to configure in app.config.js for it to work. The
 * contract is the same on both platforms: the user drops a pin (tap or
 * drag) and `onPick(lat, lng)` hands the coordinates to the parent, which
 * resolves the district.
 */
import { useEffect, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { District } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

// Self-contained Leaflet page: locked to Sri Lanka, same tile source and
// bounds as the web picker. Pin taps/drags post {lat, lng} back to RN.
const MAP_HTML = `<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { height: 100%; margin: 0; padding: 0; background: ${Palette.primaryTint}; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const lanka = L.latLngBounds([5.7, 79.4], [10.05, 82.1]);
    const map = L.map('map', { maxBounds: lanka, maxBoundsViscosity: 1.0, minZoom: 7 });
    map.fitBounds(lanka);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(map);

    const marker = L.marker([__LAT__, __LNG__], { draggable: true }).addTo(map);
    const post = (lat, lng) => window.ReactNativeWebView.postMessage(JSON.stringify({ lat, lng }));
    marker.on('dragend', () => { const p = marker.getLatLng(); post(p.lat, p.lng); });
    map.on('click', (e) => { marker.setLatLng(e.latlng); post(e.latlng.lat, e.latlng.lng); });

    map.setView([__LAT__, __LNG__], 9);

    // Bridge for RN -> WebView recentring when the selected district changes.
    document.addEventListener('message', onRNMessage);
    window.addEventListener('message', onRNMessage);
    function onRNMessage(e) {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'recenter') {
          map.setView([msg.lat, msg.lng], 9);
          marker.setLatLng([msg.lat, msg.lng]);
        }
      } catch {}
    }
  </script>
</body>
</html>`;

export function DistrictMap({ selected, pin, onPick }: Props) {
  const webRef = useRef<WebView>(null);

  const html = MAP_HTML.replaceAll('__LAT__', String(selected.lat)).replaceAll(
    '__LNG__',
    String(selected.lng),
  );

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
