/**
 * lib/api.ts — the bridge to the FastAPI backend.
 *
 * fetchForecastBundle() pulls one 24-hour GRU run from the server and returns
 * it in two shapes at once:
 *   - `prediction`: the clock-hour Prediction the existing UI consumes
 *   - `live`:       the +1..+24 sequence with advisories and the daily summary
 * Every successful call is cached in AsyncStorage for 24 hours (factor 4);
 * the server independently persists the run to Supabase (forecast_runs) and
 * tops up weather_observations.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { districtByKey, districts } from '../constants/districts';
import { HourPrediction, Prediction, predict } from './engine';

// Point this at the machine running `uvicorn main:app`. For a phone on the
// same Wi-Fi, set EXPO_PUBLIC_API_URL=http://<your-PC-LAN-IP>:8000 in .env —
// localhost on a phone is the phone itself.
export const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

// The current session token, set by the auth provider. Kept module-level so
// data functions can attach it without importing React context.
let authToken: string | null = null;
export const setAuthToken = (token: string | null) => {
  authToken = token;
};
export const authHeaders = (): Record<string, string> =>
  authToken ? { Authorization: `Bearer ${authToken}` } : {};

/** Backend district keys have no spaces: 'Nuwara Eliya' → 'NuwaraEliya'. */
const apiName = (districtKey: string) => {
  const d = districtByKey(districtKey);
  return d ? d.name.replace(/\s+/g, '') : districtKey;
};

export type AdvisoryLevel = 'GOOD' | 'CAUTION' | 'AVOID';

export type Hour24 = {
  offset: number;        // +1 .. +24 hours from the model run
  validTime: string;     // "2026-07-15 14:00" local (Asia/Colombo)
  label: string;         // "2 PM"
  temp: number;
  rain: number;
  humidity: number;
  advisoryLevel: AdvisoryLevel;
  advisoryReason: string;
};

export type Summary24 = {
  tempMin: number;
  tempMax: number;
  tempAvg: number;
  totalRain: number;
  humidityMin: number;
  humidityMax: number;
  wetHours: number;
  advisoryLevel: AdvisoryLevel;
  verdict: string;
};

export type Forecast24 = {
  districtKey: string;
  origin: string;
  hours: Hour24[];
  summary: Summary24;
};

export type ForecastBundle = {
  prediction: Prediction;
  live: Forecast24;
};

type ApiHour = {
  forecast_hour: number;
  valid_time: string;
  temperature_c: number;
  precipitation_mm: number;
  humidity_pct: number;
  advisory_level: AdvisoryLevel;
  advisory_reason: string;
};

type ApiResponse = {
  district: string;
  forecast_origin: string;
  cached: boolean;
  summary: {
    temp_min_c: number;
    temp_max_c: number;
    temp_avg_c: number;
    total_rain_mm: number;
    humidity_min_pct: number;
    humidity_max_pct: number;
    wet_hours: number;
    advisory_level: AdvisoryLevel;
    verdict: string;
  };
  forecast: ApiHour[];
};

const hourLabel = (clockHour: number) => {
  const suffix = clockHour >= 12 ? 'PM' : 'AM';
  const h = clockHour % 12 === 0 ? 12 : clockHour % 12;
  return `${h} ${suffix}`;
};

/**
 * One 24-hour forecast from the GRU on the server. The model predicts
 * temperature, rain and humidity; wind is not a model output, so those values
 * are kept from the local baseline rather than invented.
 */
export async function fetchForecastBundle(
  districtKey: string,
  opts: { refresh?: boolean } = {},
): Promise<ForecastBundle> {
  const query = opts.refresh ? '?refresh=true' : '';
  const res = await fetch(`${API_BASE}/api/v1/forecast/${apiName(districtKey)}${query}`);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  const data: ApiResponse = await res.json();

  const baseline = predict(districtKey); // supplies wind + fills unforecast hours
  const hours: HourPrediction[] = baseline.hours.map((h) => ({ ...h }));
  const live: Hour24[] = [];

  for (const f of data.forecast) {
    const clockHour = parseInt(f.valid_time.slice(11, 13), 10);
    if (Number.isNaN(clockHour)) continue;

    hours[clockHour] = {
      hour: clockHour,
      temp: f.temperature_c,
      rain: f.precipitation_mm,
      humidity: f.humidity_pct,
      wind: hours[clockHour].wind,
    };

    live.push({
      offset: f.forecast_hour,
      validTime: f.valid_time,
      label: hourLabel(clockHour),
      temp: f.temperature_c,
      rain: f.precipitation_mm,
      humidity: f.humidity_pct,
      advisoryLevel: f.advisory_level,
      advisoryReason: f.advisory_reason,
    });
  }

  return {
    prediction: { districtKey, generatedAt: Date.now(), hours },
    live: {
      districtKey,
      origin: data.forecast_origin,
      hours: live,
      summary: {
        tempMin: data.summary.temp_min_c,
        tempMax: data.summary.temp_max_c,
        tempAvg: data.summary.temp_avg_c,
        totalRain: data.summary.total_rain_mm,
        humidityMin: data.summary.humidity_min_pct,
        humidityMax: data.summary.humidity_max_pct,
        wetHours: data.summary.wet_hours,
        advisoryLevel: data.summary.advisory_level,
        verdict: data.summary.verdict,
      },
    },
  };
}

// ── Weekly outlook — GRU rollout for the climate-disruption planner ──────────

export type OutlookDay = {
  date: string;          // "2026-07-18"
  weekday: string;       // "Saturday"
  source: 'gru' | 'gru+pattern';
  confidence: 'high' | 'medium' | 'low';
  tempMin: number;
  tempMax: number;
  tempAvg: number;
  totalRain: number;
  wetHours: number;
  advisoryLevel: AdvisoryLevel;
  verdict: string;
};

type ApiWeeklyDay = {
  date: string;
  weekday: string;
  hours_covered: number;
  source: string;
  confidence: string;
  temp_min_c: number;
  temp_max_c: number;
  temp_avg_c: number;
  total_rain_mm: number;
  wet_hours: number;
  advisory_level: AdvisoryLevel;
  verdict: string;
};

/**
 * 7 days, every one a GRU prediction. Day 1 is the standard forecast; later
 * days are autoregressive rollouts where the model's own output extends its
 * input window and unpredicted channels follow the past week's hourly pattern.
 */
export async function fetchWeeklyOutlook(districtKey: string): Promise<OutlookDay[]> {
  const res = await fetch(`${API_BASE}/api/v1/forecast/weekly/${apiName(districtKey)}`);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  const data: { days: ApiWeeklyDay[] } = await res.json();
  return data.days.map((d) => ({
    date: d.date,
    weekday: d.weekday,
    source: d.source === 'gru' ? 'gru' : 'gru+pattern',
    confidence: (['high', 'medium', 'low'].includes(d.confidence) ? d.confidence : 'low') as
      | 'high'
      | 'medium'
      | 'low',
    tempMin: d.temp_min_c,
    tempMax: d.temp_max_c,
    tempAvg: d.temp_avg_c,
    totalRain: d.total_rain_mm,
    wetHours: d.wet_hours,
    advisoryLevel: d.advisory_level,
    verdict: d.verdict,
  }));
}

// ── Current conditions — live Open-Meteo snapshot, no model ──────────────────

export type CurrentConditions = {
  districtKey: string;
  observedAt: string;    // "2026-07-16T13:00" local (Asia/Colombo)
  temp: number;
  feelsLike: number;
  humidity: number;
  rain: number;
  cloudCover: number;
  pressure: number;
  windSpeed: number;
  windGusts: number;
  windDirection: number; // degrees
  uvIndex: number;
  isDay: boolean;
  condition: string;     // "Partly cloudy", "Light drizzle", ...
};

type ApiCurrent = {
  district: string;
  observed_at: string;
  temperature_c: number;
  feels_like_c: number;
  humidity_pct: number;
  precipitation_mm: number;
  cloud_cover_pct: number;
  pressure_msl_hpa: number;
  wind_speed_kmh: number;
  wind_gusts_kmh: number;
  wind_direction_deg: number;
  uv_index: number;
  is_day: boolean;
  condition: string;
};

/** What the sky is doing in a district right now — for the "go now" comparison. */
export async function fetchCurrentConditions(districtKey: string): Promise<CurrentConditions> {
  const res = await fetch(`${API_BASE}/api/v1/forecast/current/${apiName(districtKey)}`);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  const c: ApiCurrent = await res.json();
  return {
    districtKey,
    observedAt: c.observed_at,
    temp: c.temperature_c,
    feelsLike: c.feels_like_c,
    humidity: c.humidity_pct,
    rain: c.precipitation_mm,
    cloudCover: c.cloud_cover_pct,
    pressure: c.pressure_msl_hpa,
    windSpeed: c.wind_speed_kmh,
    windGusts: c.wind_gusts_kmh,
    windDirection: c.wind_direction_deg,
    uvIndex: c.uv_index,
    isDay: c.is_day,
    condition: c.condition,
  };
}

// ── Ground reports (factor 10) — crowd-sourced, 24-hour lifetime ─────────────

const keyByApiName: Record<string, string> = Object.fromEntries(
  districts.map((d) => [d.name.replace(/\s+/g, ''), d.key]),
);

export type GroundReport = {
  id: string;
  districtKey: string;
  districtName: string;
  location: string;
  title: string;
  body: string;
  author: string; // username of the logged-in reporter
  authorAvatar: string; // reporter's profile-picture URL, may be ''
  at: number; // epoch ms
};

type ApiReport = {
  id: string;
  district: string;
  location: string;
  title: string;
  body: string;
  author?: string;
  author_avatar?: string;
  created_at: string;
};

export async function fetchGroundReports(opts: {
  districtKey?: string;
  search?: string;
} = {}): Promise<GroundReport[]> {
  const params = new URLSearchParams();
  if (opts.districtKey) params.set('district', apiName(opts.districtKey));
  if (opts.search?.trim()) params.set('search', opts.search.trim());
  const qs = params.toString();

  const res = await fetch(`${API_BASE}/api/v1/reports${qs ? `?${qs}` : ''}`);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  const data: { reports: ApiReport[] } = await res.json();

  return data.reports.map((r) => ({
    id: r.id,
    districtKey: keyByApiName[r.district] ?? r.district.toLowerCase(),
    districtName: districtByKey(keyByApiName[r.district])?.name ?? r.district,
    location: r.location,
    title: r.title,
    body: r.body,
    author: r.author ?? '',
    authorAvatar: r.author_avatar ?? '',
    at: new Date(r.created_at).getTime(),
  }));
}

export async function postGroundReport(report: {
  districtKey: string;
  location: string;
  title: string;
  body: string;
}): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      district: apiName(report.districtKey),
      location: report.location,
      title: report.title,
      body: report.body,
    }),
  });
  if (res.status === 401) {
    throw new Error('LOGIN_REQUIRED');
  }
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
}

/** Delete one of YOUR OWN ground reports. Login required. */
export async function deleteGroundReport(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/reports/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (res.status === 401) throw new Error('LOGIN_REQUIRED');
  if (!res.ok && res.status !== 404) throw new Error(`Backend returned ${res.status}`);
}

// ── Travel notebook — private, login required ────────────────────────────────

export type TravelNote = {
  id: string;
  place: string;
  body: string;
  at: number; // epoch ms
};

type ApiNote = { id: string; place: string; body: string; created_at: string };

export async function fetchTravelNotes(): Promise<TravelNote[]> {
  const res = await fetch(`${API_BASE}/api/v1/notes`, { headers: authHeaders() });
  if (res.status === 401) throw new Error('LOGIN_REQUIRED');
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  const data: { notes: ApiNote[] } = await res.json();
  return data.notes.map((n) => ({
    id: n.id,
    place: n.place,
    body: n.body,
    at: new Date(n.created_at).getTime(),
  }));
}

export async function postTravelNote(note: { place: string; body: string }): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(note),
  });
  if (res.status === 401) throw new Error('LOGIN_REQUIRED');
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
}

export async function deleteTravelNote(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/notes/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (res.status === 401) throw new Error('LOGIN_REQUIRED');
  if (!res.ok && res.status !== 404) throw new Error(`Backend returned ${res.status}`);
}

// ── Offline cache (factor 4) — expires after 24 hours ────────────────────────

const CACHE_TTL_MS = 24 * 60 * 60 * 1000;

type CachedRun = { at: number; bundle: ForecastBundle };

const cacheKey = (districtKey: string) => `forecast:${districtKey}`;

export async function cacheForecast(districtKey: string, bundle: ForecastBundle) {
  try {
    const entry: CachedRun = { at: Date.now(), bundle };
    await AsyncStorage.setItem(cacheKey(districtKey), JSON.stringify(entry));
  } catch {
    // Cache writes are best-effort; the user already has their forecast.
  }
}

export async function loadCachedForecast(districtKey: string): Promise<CachedRun | null> {
  try {
    const raw = await AsyncStorage.getItem(cacheKey(districtKey));
    if (!raw) return null;
    const entry = JSON.parse(raw) as CachedRun;
    if (Date.now() - entry.at > CACHE_TTL_MS) {
      // A prediction older than its own horizon is not a forecast any more.
      await AsyncStorage.removeItem(cacheKey(districtKey));
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}
