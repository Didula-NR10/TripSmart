import { useEffect, useRef } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';
import MapView, { MapPressEvent, Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { District } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

// Frames the whole island with a little breathing room.
const SRI_LANKA = {
  latitude: 7.87,
  longitude: 80.77,
  latitudeDelta: 4.6,
  longitudeDelta: 3.4,
};

export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

export function DistrictMap({ selected, pin, onPick }: Props) {
  const mapRef = useRef<MapView>(null);

  // District chosen from the search sheet (pin cleared by the parent): recentre on it.
  useEffect(() => {
    if (pin) return;
    mapRef.current?.animateToRegion(
      { latitude: selected.lat, longitude: selected.lng, latitudeDelta: 0.9, longitudeDelta: 0.9 },
      350,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.key]);

  const onPress = (e: MapPressEvent) => {
    const { latitude, longitude } = e.nativeEvent.coordinate;
    onPick(latitude, longitude);
  };

  return (
    <View style={styles.wrap}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        provider={Platform.OS === 'android' ? PROVIDER_GOOGLE : undefined}
        initialRegion={SRI_LANKA}
        onPress={onPress}
        toolbarEnabled={false}
        showsCompass={false}
        showsMyLocationButton={false}
      >
        <Marker
          coordinate={pin ?? { latitude: selected.lat, longitude: selected.lng }}
          title={`${selected.name} District`}
          description="Forecast runs for this district"
        />
      </MapView>

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
