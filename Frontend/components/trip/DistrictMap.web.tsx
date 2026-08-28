import { useEffect, useRef, useState, type CSSProperties } from 'react';
import Constants from 'expo-constants';
import { District } from '../../constants/districts';
import { Palette, Radius } from '../../constants/trip-theme';
import { geocodePlace } from '../../lib/api';

export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

const GOOGLE_MAPS_API_KEY: string =
  (Constants.expoConfig?.extra as any)?.googleMapsApiKey ?? '';

const SRI_LANKA_BOUNDS = { south: 5.7, west: 79.4, north: 10.05, east: 82.1 };

let googleLoader: Promise<any> | null = null;

function loadGoogleMaps(): Promise<any> {
  const w = window as any;
  if (w.google?.maps) return Promise.resolve(w.google);
  if (!googleLoader) {
    googleLoader = new Promise((resolve, reject) => {
      const cbName = '__tripsmartGoogleMapsReady';
      w[cbName] = () => resolve(w.google);
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&callback=${cbName}`;
      script.async = true;
      script.onerror = () => reject(new Error('Google Maps failed to load'));
      document.head.appendChild(script);
    });
  }
  return googleLoader;
}

export function DistrictMap({ selected, pin, onPick }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [notice, setNotice] = useState<string | null>(
    GOOGLE_MAPS_API_KEY ? null : 'No Google Maps API key configured (app.config.js).',
  );

  // The map handlers live as long as the map; keep the latest onPick in a ref.
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  // Build the map once.
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) return;
    let disposed = false;

    loadGoogleMaps()
      .then((google) => {
        if (disposed || !holder.current || mapRef.current) return;

        const map = new google.maps.Map(holder.current, {
          center: { lat: selected.lat, lng: selected.lng },
          zoom: 9,
          minZoom: 7,
          restriction: {
            latLngBounds: SRI_LANKA_BOUNDS,
            strictBounds: false,
          },
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        });
        (window as any).__lankaMap = map; // exposed for automated UI tests

        const marker = new google.maps.Marker({
          position: { lat: selected.lat, lng: selected.lng },
          map,
          draggable: true,
        });
        marker.addListener('dragend', () => {
          const p = marker.getPosition();
          onPickRef.current(p.lat(), p.lng());
        });
        map.addListener('click', (e: any) => {
          marker.setPosition(e.latLng);
          onPickRef.current(e.latLng.lat(), e.latLng.lng());
        });

        mapRef.current = map;
        markerRef.current = marker;
      })
      .catch(() => setNotice('Map tiles could not be loaded. Use the district dropdown below.'));

    return () => {
      disposed = true;
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // District chosen from the dropdown (pin cleared by the parent): recentre.
  useEffect(() => {
    if (pin || !mapRef.current) return;
    mapRef.current.setCenter({ lat: selected.lat, lng: selected.lng });
    mapRef.current.setZoom(9);
    markerRef.current?.setPosition({ lat: selected.lat, lng: selected.lng });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.key]);

  // Geocoding proxied through the backend (Google Geocoding API server-side),
  // so the app never ships a client key with geocoding privileges.
  const search = async () => {
    const q = query.trim();
    if (!q || searching) return;
    setSearching(true);
    setNotice(null);
    try {
      const { lat, lon } = await geocodePlace(q);
      mapRef.current?.setCenter({ lat, lng: lon });
      mapRef.current?.setZoom(11);
      markerRef.current?.setPosition({ lat, lng: lon });
      onPick(lat, lon);
    } catch (err: any) {
      setNotice(err?.message?.includes('not found')
        ? `"${q}" not found in Sri Lanka — try a town or landmark name.`
        : 'Search failed. Check your connection and try again.');
    } finally {
      setSearching(false);
    }
  };

  const shownLat = pin ? pin.latitude : selected.lat;
  const shownLng = pin ? pin.longitude : selected.lng;

  return (
    <div style={ui.wrap}>
      <div style={ui.searchRow}>
        <input
          style={ui.input}
          value={query}
          placeholder="Search a place — e.g. Ella, Sigiriya, Mirissa"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') search();
          }}
        />
        <button style={ui.button} onClick={search} disabled={searching}>
          {searching ? 'Finding…' : 'Find'}
        </button>
      </div>

      <div style={ui.mapBox}>
        <div ref={holder} style={ui.map} />
        <div style={ui.hint}>Tap, drag the pin, or search — it resolves to its district</div>
        <div style={ui.legend}>📍 {selected.name}</div>
      </div>

      <div style={ui.coords}>
        <span style={ui.coordsMono}>
          {shownLat.toFixed(6)}, {shownLng.toFixed(6)}
        </span>
        <span style={ui.coordsNote}>
          → {selected.name} district · forecast uses the district&apos;s coordinates
        </span>
      </div>

      {notice ? <div style={ui.notice}>{notice}</div> : null}
    </div>
  );
}

const ui: Record<string, CSSProperties> = {
  wrap: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  searchRow: {
    display: 'flex',
    gap: 8,
  },
  input: {
    flex: 1,
    padding: '10px 12px',
    borderRadius: Radius.md,
    border: `1px solid ${Palette.border}`,
    fontSize: 13,
    fontFamily: 'inherit',
    color: Palette.text,
    outline: 'none',
    backgroundColor: Palette.surface,
  },
  button: {
    padding: '10px 18px',
    borderRadius: Radius.md,
    border: 'none',
    backgroundColor: Palette.primary,
    color: '#fff',
    fontWeight: 700,
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  mapBox: {
    position: 'relative',
    height: 300,
    borderRadius: Radius.xl,
    border: `1px solid ${Palette.border}`,
    overflow: 'hidden',
    backgroundColor: Palette.primaryTint,
  },
  map: {
    position: 'absolute',
    inset: 0,
  },
  hint: {
    position: 'absolute',
    top: 10,
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 1000,
    backgroundColor: Palette.surface,
    borderRadius: 999,
    padding: '5px 12px',
    fontSize: 10,
    color: Palette.textMuted,
    whiteSpace: 'nowrap',
    boxShadow: '0 1px 4px rgba(9, 34, 38, 0.15)',
  },
  legend: {
    position: 'absolute',
    bottom: 10,
    left: 10,
    zIndex: 1000,
    backgroundColor: Palette.surface,
    borderRadius: 999,
    padding: '6px 12px',
    fontSize: 12,
    fontWeight: 700,
    color: Palette.text,
    boxShadow: '0 1px 4px rgba(9, 34, 38, 0.15)',
  },
  coords: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 8,
    flexWrap: 'wrap',
    backgroundColor: Palette.canvas,
    borderRadius: Radius.md,
    padding: '8px 12px',
  },
  coordsMono: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: Palette.text,
  },
  coordsNote: {
    fontSize: 11,
    color: Palette.textMuted,
  },
  notice: {
    fontSize: 11,
    color: '#7E2A20',
    backgroundColor: Palette.dangerSoft,
    borderRadius: Radius.md,
    padding: '8px 12px',
  },
};
