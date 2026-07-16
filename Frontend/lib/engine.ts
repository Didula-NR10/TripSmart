import { districts, District, districtByKey } from '../constants/districts';
import { zones, Zone } from '../constants/geofences';
import { poyaDays2026 } from '../constants/poya';
import { Profile, ProfileKey, profileByKey } from '../constants/profiles';

export type HourPrediction = {
  hour: number;
  temp: number;
  rain: number;
  humidity: number;
  wind: number;
};

export type Prediction = {
  districtKey: string;
  generatedAt: number;
  hours: HourPrediction[];
};

export function resolveDistrict(lat: number, lng: number): District | null {
  const hit = districts.find(
    (d) => lat >= d.bbox[0] && lat <= d.bbox[2] && lng >= d.bbox[1] && lng <= d.bbox[3],
  );
  if (hit) {
    return hit;
  }
  return nearestDistrict(lat, lng);
}

export function nearestDistrict(lat: number, lng: number): District | null {
  let best: District | null = null;
  let bestDistance = Infinity;
  for (const d of districts) {
    const distance = haversineKm(lat, lng, d.lat, d.lng);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = d;
    }
  }
  return bestDistance <= 60 ? best : null;
}

export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number) {
  const toRad = (v: number) => (v * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function seedFrom(text: string) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) % 100000;
  }
  return hash;
}

export function predict(districtKey: string): Prediction {
  const district = districtByKey(districtKey);
  const seed = seedFrom(districtKey) + new Date().getDate();
  const lapse = district ? district.elevation / 150 : 0;
  const wetBias = district?.zone === 'wet' ? 1.6 : district?.zone === 'dry' ? 0.25 : 0.8;

  const hours: HourPrediction[] = [];
  for (let h = 0; h < 24; h++) {
    const diurnal = Math.sin(((h - 9) / 24) * Math.PI * 2);
    const noise = Math.sin(seed + h * 1.7) * 0.9;
    const temp = 28.5 - lapse + diurnal * 4.2 + noise;
    const rainPeak = Math.max(0, Math.sin(((h - 14) / 12) * Math.PI));
    const rain = Math.max(0, rainPeak * wetBias * (1 + Math.sin(seed + h)) * 0.8);
    const humidity = 62 + rain * 6 + Math.sin(seed * 0.5 + h / 3) * 8;
    const wind = 8 + Math.abs(Math.sin(seed + h / 4)) * 14;
    hours.push({
      hour: h,
      temp: round(temp, 1),
      rain: round(rain, 1),
      humidity: clamp(round(humidity, 0), 40, 98),
      wind: round(wind, 0),
    });
  }
  return { districtKey, generatedAt: Date.now(), hours };
}

const round = (v: number, dp: number) => Number(v.toFixed(dp));
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export type Window = { from: number; to: number; score: number } | null;

export function bestWindow(prediction: Prediction, profile: Profile): Window {
  const span = 4;
  let best: Window = null;
  for (let start = 6; start + span <= 19; start++) {
    const slice = prediction.hours.slice(start, start + span);
    const score = slice.reduce((sum, h) => sum + scoreHour(h, profile), 0) / span;
    if (!best || score > best.score) {
      best = { from: start, to: start + span, score: round(score, 1) };
    }
  }
  return best;
}

export function scoreHour(hour: HourPrediction, profile: Profile) {
  let score = 100;
  const [lo, hi] = profile.idealTemp;
  if (hour.temp < lo) score -= (lo - hour.temp) * 6;
  if (hour.temp > hi) score -= (hour.temp - hi) * 7;
  if (hour.rain > profile.maxRain) score -= (hour.rain - profile.maxRain) * 22;
  if (hour.humidity > profile.maxHumidity) score -= (hour.humidity - profile.maxHumidity) * 1.4;
  if (hour.wind > profile.maxWind) score -= (hour.wind - profile.maxWind) * 1.2;
  return clamp(score, 0, 100);
}

export function gradeDay(prediction: Prediction, profileKey: ProfileKey) {
  const profile = profileByKey(profileKey);
  const daylight = prediction.hours.filter((h) => h.hour >= 6 && h.hour <= 18);
  const mean = daylight.reduce((sum, h) => sum + scoreHour(h, profile), 0) / daylight.length;
  return { score: Math.round(mean), letter: toLetter(mean), profile };
}

function toLetter(score: number) {
  if (score >= 92) return 'A+';
  if (score >= 85) return 'A';
  if (score >= 78) return 'B+';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C+';
  if (score >= 50) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}

export function totalRain(prediction: Prediction) {
  return round(prediction.hours.reduce((sum, h) => sum + h.rain, 0), 1);
}

export type Alternative = { district: District; rain: number; driveKm: number } | null;

export function suggestAlternative(
  districtKey: string,
  prediction: Prediction,
  radiusKm = 140,
): Alternative {
  if (totalRain(prediction) < 8) {
    return null;
  }
  const origin = districtByKey(districtKey);
  if (!origin) return null;

  let best: Alternative = null;
  for (const d of districts) {
    if (d.key === origin.key) continue;
    const driveKm = haversineKm(origin.lat, origin.lng, d.lat, d.lng);
    if (driveKm > radiusKm) continue;
    const rain = totalRain(predict(d.key));
    if (rain > 3) continue;
    if (!best || rain < best.rain) {
      best = { district: d, rain, driveKm: Math.round(driveKm) };
    }
  }
  return best;
}

export function zonesNear(lat: number, lng: number): Zone[] {
  return zones.filter((z) => haversineKm(lat, lng, z.lat, z.lng) <= z.radiusKm);
}

/** Every advisory zone that sits inside a district — not just near its centre. */
export function zonesInDistrict(districtKey: string): Zone[] {
  return zones.filter((z) => resolveDistrict(z.lat, z.lng)?.key === districtKey);
}

export function poyaToday(now = new Date()) {
  const iso = now.toISOString().slice(0, 10);
  return poyaDays2026.find((p) => p.date === iso) ?? null;
}

export function nextPoya(now = new Date()) {
  const iso = now.toISOString().slice(0, 10);
  return poyaDays2026.find((p) => p.date >= iso) ?? null;
}

export function fuelEfficiency(startOdo: number, endOdo: number, litres: number) {
  const distance = endOdo - startOdo;
  if (distance <= 0 || litres <= 0) return null;
  const kmPerLitre = distance / litres;
  return {
    distance: Math.round(distance),
    kmPerLitre: round(kmPerLitre, 1),
    litresPer100: round(100 / kmPerLitre, 1),
  };
}

export function hillPenalty(districtKey: string) {
  const d = districtByKey(districtKey);
  if (!d) return 0;
  if (d.elevation >= 1000) return 20;
  if (d.elevation >= 400) return 12;
  return 0;
}
