import { District } from '../../constants/districts';
import { MapCanvas } from './MapCanvas';

// react-native-maps has no web build; the schematic canvas keeps `npx expo start --web` usable.
export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

export function DistrictMap({ selected, onPick }: Props) {
  return <MapCanvas selected={selected} onPick={onPick} />;
}
