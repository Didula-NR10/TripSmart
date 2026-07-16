/**
 * DistrictMap.web.tsx — real map picker for the browser.
 *
 * react-native-maps has no web build, so the web version uses Leaflet with
 * free OpenStreetMap tiles instead (no API key needed). The contract is the
 * same as the native map: the user drops a pin (tap, drag, or search) and
 * `onPick(lat, lng)` hands the coordinates to the parent, which resolves the
 * district — the forecast then runs on that district's own coordinates
 * through the unchanged 7-days-back + GRU pipeline.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { District } from '../../constants/districts';
import { Palette, Radius } from '../../constants/trip-theme';

export type MapPin = { latitude: number; longitude: number } | null;

type Props = {
  selected: District;
  pin: MapPin;
  onPick: (lat: number, lng: number) => void;
};

const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';

let leafletLoader: Promise<any> | null = null;

function loadLeaflet(): Promise<any> {
  const w = window as any;
  if (w.L) return Promise.resolve(w.L);
  if (!leafletLoader) {
    leafletLoader = new Promise((resolve, reject) => {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = LEAFLET_CSS;
      document.head.appendChild(css);

      const script = document.createElement('script');
      script.src = LEAFLET_JS;
      script.onload = () => resolve(w.L);
      script.onerror = () => reject(new Error('Leaflet failed to load'));
      document.head.appendChild(script);
    });
  }
  return leafletLoader;
}

export function DistrictMap({ selected, pin, onPick }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // The map handlers live as long as the map; keep the latest onPick in a ref.
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  // Build the map once.
  useEffect(() => {
    let disposed = false;

    loadLeaflet()
      .then((L) => {
        if (disposed || !holder.current || mapRef.current) return;

        // Hard-lock the view to Sri Lanka: users cannot pan away to another
        // country, and minZoom stops zooming out to the world map.
        const lanka = L.latLngBounds([5.7, 79.4], [10.05, 82.1]);
        const map = L.map(holder.current, {
          maxBounds: lanka,
          maxBoundsViscosity: 1.0,
          minZoom: 7,
        });
        map.fitBounds(lanka);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '© OpenStreetMap contributors',
        }).addTo(map);
        (window as any).__lankaMap = map; // exposed for automated UI tests

        const marker = L.marker([selected.lat, selected.lng], { draggable: true }).addTo(map);
        marker.on('dragend', () => {
          const p = marker.getLatLng();
          onPickRef.current(p.lat, p.lng);
        });
        map.on('click', (e: any) => {
          marker.setLatLng(e.latlng);
          onPickRef.current(e.latlng.lat, e.latlng.lng);
        });

        mapRef.current = map;
        markerRef.current = marker;
      })
      .catch(() => setNotice('Map tiles could not be loaded. Use the district dropdown below.'));

    return () => {
      disposed = true;
      mapRef.current?.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // District chosen from the dropdown (pin cleared by the parent): recentre.
  useEffect(() => {
    if (pin || !mapRef.current) return;
    mapRef.current.setView([selected.lat, selected.lng], 9);
    markerRef.current?.setLatLng([selected.lat, selected.lng]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.key]);

  // Free geocoding via OpenStreetMap's Nominatim, biased to Sri Lanka.
  const search = async () => {
    const q = query.trim();
    if (!q || searching) return;
    setSearching(true);
    setNotice(null);
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=lk&q=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        const lat = parseFloat(data[0].lat);
        const lng = parseFloat(data[0].lon);
        mapRef.current?.setView([lat, lng], 11);
        markerRef.current?.setLatLng([lat, lng]);
        onPick(lat, lng);
      } else {
        setNotice(`"${q}" not found in Sri Lanka — try a town or landmark name.`);
      }
    } catch {
      setNotice('Search failed. Check your connection and try again.');
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
