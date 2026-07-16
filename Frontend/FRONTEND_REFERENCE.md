# Trip Smart — Frontend Reference

Expo SDK 54. Routes at `app/`, all imports relative, no path alias.

---

## Install

Everything is already in your project except these:

```
npx expo install react-native-svg expo-linear-gradient @expo/vector-icons @expo-google-fonts/inter
```

Then empty the routes folder and unzip at the project root:

```
Remove-Item -Recurse -Force app\*
npx expo start -c
```

---

## The central idea

Every feature in this app is a function of two values:

```
(latitude, longitude) → districtKey → prediction[24]
```

Resolve the pin to a district. Run the model for that district. Everything else — the
grade, the best window, the alternative suggestion, the cuisine card, the almanac
comparison — is a pure function over those two things. There is no second data source.

That is why `lib/engine.ts` exists as a separate layer. Today it computes predictions
locally with a deterministic synthetic model. When Flask is live, you replace **one
function** (`predict`) with a `fetch` call and nothing else in the app changes.

---

## Where each of the 14 features lives

| # | Feature | Tab | File |
|---|---------|-----|------|
| 1 | Coordinates → district | Explore | `lib/engine.ts` → `resolveDistrict` |
| 2 | Offline smart cache | Profile | `lib/store.tsx` → `offline`, `cachedAt` |
| 3 | Microclimate suggestion | Today | `engine.suggestAlternative` |
| 4 | Best-window watch | Plan | `engine.bestWindow`, `store.watches` |
| 5 | Traveler profile matching | Profile / Today | `engine.gradeDay`, `constants/profiles.ts` |
| 6 | Two-district comparer | Plan | `components/trip/Comparer.tsx` |
| 7 | Climate-disruption planner | Plan | `components/trip/HybridTimeline.tsx` |
| 8 | Crowdsourced ground truth | Explore | `components/trip/CommunityFeed.tsx` |
| 9 | Historical almanac | Almanac | `components/trip/AlmanacChart.tsx` |
| 10 | Cultural etiquette guardian | Explore | `constants/geofences.ts` + `ZoneModal` |
| 11 | Drone / high-security zones | Explore | same file, `kind: 'restricted'` |
| 12 | Poya day monitor | Today / Profile | `engine.poyaToday`, `constants/poya.ts` |
| 13 | Tuk-tuk fuel calculator | Profile | `components/trip/FuelCalculator.tsx` |
| 14 | Regional culinary explorer | Today / Explore | `constants/cuisine.ts` + `CuisineCard` |

---

## `lib/engine.ts` — the logic layer

This is the file your examiners will read. Everything here is a pure function with no
UI, no state and no side effects.

### Geofencing

**`resolveDistrict(lat, lng) → District | null`**
Feature 1. Runs a bounding-box test against all 25 districts. If the pin falls in no
box (sea, border gaps), it falls back to `nearestDistrict`.

*Honest limitation:* bounding boxes are rectangles; real district borders are polygons.
Neighbouring districts overlap slightly, so a pin near a border may resolve to the wrong
one. **Fix this on the backend** with a real GeoJSON point-in-polygon test. The rectangles
are here so the UI works before the backend exists — not as the final algorithm.

**`nearestDistrict(lat, lng)`** — falls back to the closest centroid within 60 km.

**`haversineKm(lat1, lng1, lat2, lng2)`** — great-circle distance. Used by district
fallback, alternative suggestion, and geofence radius checks.

**`zonesNear(lat, lng) → Zone[]`**
Features 10 and 11. Returns every cultural site or restricted zone whose radius contains
the pin. One function serves both features; they differ only by the `kind` field.

### Prediction

**`predict(districtKey) → Prediction`**
**This is the function you replace.** Today it generates a deterministic 24-hour vector
from a seeded sine model, adjusted for elevation (lapse rate) and wet/dry zone. Same
district always gives the same result, so the UI is stable while you develop.

When Flask is live:

```ts
export async function predict(districtKey: string): Promise<Prediction> {
  const res = await fetch(`${API}/predict?district=${districtKey}`);
  return res.json();
}
```

Keep the return shape identical — `{ districtKey, generatedAt, hours: HourPrediction[] }`
where each hour is `{ hour, temp, rain, humidity, wind }`. Nothing else in the app
needs to change.

**`totalRain(prediction)`** — sums 24 hours of precipitation. Used by the microclimate
rule and the comparer.

### Scoring

**`scoreHour(hour, profile) → 0..100`**
Feature 5, the core of it. Starts at 100 and subtracts penalties: temperature outside the
profile's ideal band, rain above tolerance, humidity above tolerance, wind above tolerance.
Each profile has different thresholds, so the *same* hour scores differently for a Hiker
and a Beach Lover. That is the entire mechanism.

**`gradeDay(prediction, profileKey) → { score, letter, profile }`**
Averages `scoreHour` across daylight hours (06:00–18:00) and maps to a letter grade.
A+ at 92, down to F below 40.

**`bestWindow(prediction, profile) → { from, to, score } | null`**
Feature 4. Slides a 4-hour window across 06:00–19:00 and returns the highest-scoring
position. Note it is **profile-dependent** — the best window for a Hiker is not the best
window for a Beach Lover, which is the point.

**`suggestAlternative(districtKey, prediction, radiusKm) → Alternative | null`**
Feature 3. If total rain exceeds 8 mm, searches every district within 140 km and returns
the driest one with under 3 mm forecast. Returns `null` when the weather is fine, which is
how the Today banner knows to stay hidden.

### Utilities

**`poyaToday()` / `nextPoya()`** — Feature 12. Static array lookup against
`constants/poya.ts`.

**`fuelEfficiency(startOdo, endOdo, litres)`** — Feature 13. Returns km/litre,
distance, and L/100km. Returns `null` on invalid input rather than `NaN`.

**`hillPenalty(districtKey)`** — Returns 20% above 1000 m, 12% above 400 m, else 0.
Drives the Central Highlands warning in the fuel calculator.

---

## `lib/store.tsx` — app state

React Context. One provider, wrapped around the tab navigator.

| Value | Purpose |
|-------|---------|
| `districtKey` / `setDistrictKey` | The selected district. Everything reads from this. |
| `profileKey` / `setProfileKey` | Traveler type. Changes every grade in the app. |
| `offline` / `toggleOffline` | Feature 2. Simulates cache fallback. |
| `prediction` | `useMemo(() => predict(districtKey))` — recomputes only when district changes. |
| `cachedAt` | Timestamp of the last model run. Shown in Profile. |
| `logs` / `addLog` | Feature 8. Community reports. |
| `watches` / `toggleWatch` | Feature 4. Watched districts. |

**Replace with real persistence** by swapping `useState` for AsyncStorage or SQLite.
The interface stays the same.

---

## Screens

### `app/index.tsx` — Today

The main feature. Hero (district, live temp, metrics) → best-window card with the
24-hour curve and the window lit as a band → conditional banners → hourly strip →
cuisine card.

The three banners are all conditional and usually invisible:
- offline → cache warning
- `poyaToday()` → alcohol/meat restriction
- `suggestAlternative()` → "go to Trincomalee instead"

That is deliberate. A banner that is always there is wallpaper.

### `app/explore.tsx` — Explore

Schematic map (25 district dots positioned by lat/lng). Tap → `resolveDistrict` →
`zonesNear` → geofence modal fires if the pin is inside a cultural or restricted zone.
Below: community feed filtered to the selected district, and the cuisine card.

**`MapCanvas.tsx` is a placeholder.** Google Maps needs native code and will not run in
Expo Go. Replace it with `react-native-maps` once you build with `npx expo run:android`.
The `onPick(lat, lng)` interface is already the one a real map gives you, so the swap is
one component.

### `app/plan.tsx` — Plan

Three features stacked:
- **Comparer** (6) — two districts, two curves overlaid, grades side by side, winner highlighted
- **HybridTimeline** (7) — day 1 from the GRU, days 2–6 from the 10-year baseline, with a monsoon warning when the historical rainfall for that month exceeds 180 mm
- **Watchlist** (4) — with an honest note that mobile OSes throttle background execution

### `app/almanac.tsx` — Almanac

Feature 9. District + month → a 12-bar chart where each bar is the 10-year high-to-low
range with the mean marked. Today's predicted mean is overlaid as a dashed amber line, so
you can see at a glance whether today is normal for the season.

`historicalSeries(district)` currently synthesises the data. **Replace it with a SQL
aggregation** over your SQLite import of `sri_lanka_labeled_final.xlsx`:

```sql
SELECT month,
       MAX(temp) AS high,
       MIN(temp) AS low,
       AVG(temp) AS mean,
       AVG(rain) AS rain
FROM observations
WHERE district = ?
GROUP BY month;
```

Same shape, same chart.

### `app/profile.tsx` — Profile

Traveler type selector (5) with the thresholds printed under each option — worth keeping,
because it makes the grading legible rather than magical. Fuel calculator (13). Data-saver
toggle and cache checkpoint (2). Next Poya date (12).

---

## Known limitations, stated plainly

1. **Bounding boxes are not polygons.** Border pins may resolve wrong. Fix on the backend.
2. **`predict()` is synthetic.** It is shaped like a real forecast and is deterministic, but it is not the GRU. Replace it first.
3. **The map is schematic.** Google Maps requires a development build.
4. **State is in memory.** Restart the app and reports and watches are gone. Wire AsyncStorage.
5. **The historical series is generated, not loaded.** Import the xlsx into SQLite.
6. **No moderation on community reports.** If this ships to real users, it needs some.

Each of these is a deliberate seam, not an oversight. Every one is replaceable without
touching a component.

---

## Build order from here

1. Flask: district resolution + Open-Meteo + scaler + GRU → verify the 24-hour vector
2. Swap `engine.predict` to call it
3. Dev build with `react-native-maps`, swap `MapCanvas`
4. SQLite import, swap `historicalSeries`
5. AsyncStorage for logs, watches, profile, cache
