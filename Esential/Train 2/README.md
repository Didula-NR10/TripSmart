# TripSmart 24-Hour Rainfall Model — Google Colab Training Package

Predicts **one number: total rain expected over the next 24 hours from
right now** — not 24 separate hourly values. Temperature and humidity are
untouched — they keep coming from the existing, already-good deployed
model. This is a rain-only, standalone model.

## Why this exists

Hourly rain prediction (the earlier package, `extra/output/rainfall/`)
topped out around R²=0.03 — a documented, literature-backed hard limit for
predicting *exactly which hour* rain falls. Asking "how much total over
the next day" instead of "how much at 3pm specifically" removes that
hardest part of the problem while still answering what a traveler actually
needs: is today a rainy day or not.

## Files

| File | Purpose |
|---|---|
| `config.py` | Every setting — data path, 35-feature list, hyperparameters, the memory-safe stride |
| `data_prep.py` | Loads the xlsx, engineers 35 features, builds windows with a single 24h-total rain target |
| `model.py` | The hurdle model (occurrence + amount, both single numbers now, not 24-length vectors) |
| `train_colab.py` | Trains it and prints/saves the full statistics table + every proof plot |

## The 35 features (up from 28)

Same base 12 (production contract) + same 12 carried over from the hourly
rain model (apparent temp, climate zone, peak season, rain lags/rolling) +
same 4 added for the 24h-ahead target (rain_rolling_48h/72h, temp/humidity
24h trend), **plus 7 NEW real atmospheric fields**:

- `DewPoint_C`, `Pressure_hPa`, `Pressure_Change_3h` — falling pressure is a classic direct precursor to an approaching storm; dew point is a more direct moisture measure than relative humidity alone.
- `WindDir_sin`, `WindDir_cos` — circular encoding of wind DIRECTION (not just speed, already present). In a monsoon climate, which direction the wind comes FROM indicates moist-ocean vs. dry-interior air.
- `VapourPressureDeficit_kPa` — how close the air is to saturation, independent of what humidity/dew point alone imply.
- `SoilMoisture_0_7cm` — antecedent ground wetness, feeding back into local evapotranspiration and convective triggering.

These came from Open-Meteo's free, keyless archive API, pulled and merged
by exact timestamp onto `sri_lanka_labeled_extended.xlsx` (all 25 districts,
2020-2026), **verified zero nulls** before being added. Two other candidate
fields (total column water vapour, boundary layer height) were tested and
explicitly excluded — a real ~6-month null gap (Jan-Jul 2024) was found for
both, too large to safely impute.

See `data_prep.py`'s docstring for the full reasoning per feature.

## Memory safety — the three crashes from building the hourly model don't get to repeat here

1. **Streaming window construction** — windows are written directly into pre-sized train/val/test arrays. The full "every window" combined array never exists as one object (building it and THEN sorting/splitting it needs the whole thing alive twice at once — confirmed as a real crash cause).
2. **In-place scaling** — uses the scaler's own formula (`X * scale_ + min_`) applied directly with in-place numpy operations, never `scaler.transform()` (which upcasts to float64 and returns a brand-new array — confirmed as another real ~8GB spike).
3. **`WINDOW_STRIDE = 10`** — the setting that finally ran crash-free end-to-end on Colab's free tier for the hourly model. Kept unchanged here since the memory math is driven by the same 168-hour input size, not by what the target looks like.

## How to run this in Google Colab

1. New Colab notebook. Runtime → Change runtime type → **GPU**.
2. Upload `config.py`, `data_prep.py`, `model.py`, `train_colab.py`, and **`sri_lanka_labeled_extended.parquet`** (not `.xlsx` — see below) into the same folder.
3. Run:
   ```python
   !pip install -q pyarrow
   !python train_colab.py
   ```

### Why Parquet, not .xlsx

A 169MB `.xlsx` upload to Colab failed with `zipfile.BadZipFile: File is not a
zip file` — `.xlsx` files ARE zip containers, so a browser upload that gets
truncated mid-transfer corrupts the file outright, and pandas can't open it
at all. The fix: `sri_lanka_labeled_extended.parquet` is a single-file,
columnar format that's roughly a third the size and loads far faster than
`openpyxl`'s sheet-by-sheet `.xlsx` reads — both more upload-resilient and
faster. If you ever regenerate it from the Excel source, `pandas.to_parquet`
with the `pyarrow` engine is all that's needed.
4. Expect roughly the same order of magnitude of time as the hourly model took — data loading/windowing a few minutes, then training epochs.
5. When done, everything is in `output/`.

## What you get in `output/`

| File | What it is |
|---|---|
| `rain24h_model.keras` / `rain24h_scaler.pkl` | The trained model and its fitted scaler |
| `report.json` | Every metric below, plus a full per-district breakdown |
| **`final_statistics.txt`** | The same summary table, human-readable |
| **`final_statistics.png`** | **The one table you asked for** — every metric in one image |
| `training_curves.png` | Loss curves, both heads, train vs. validation |
| `confusion_matrix.png` | Occurrence: correct/incorrect calls |
| `roc_curve.png` | Occurrence classifier's discriminative power |
| `calibration_curve.png` | Is "70% chance of rain in the next 24h" honest? |
| `amount_scatter.png` | Predicted vs. actual 24h total, rain windows only |

### Every metric produced

- **Occurrence (will it rain at all in the next 24h):** accuracy, precision, recall, F1, ROC-AUC, Brier score, full confusion matrix.
- **Amount (mm total, on windows that actually had rain):** MAE, RMSE, MSE, R².
- **Combined (what the app would actually show):** MAE, RMSE, MSE, R².
- **Per-district breakdown:** the same four combined/occurrence numbers, split out by all 25 districts, in `report.json`.

## An honest number to expect

Based on the published literature comparison already done for this project
(daily-total rainfall studies scored R²=0.8+, versus ~0.03 for hourly point
prediction), a realistic range for this 24h-total model is **R² = 0.3–0.6**,
possibly higher — a real, structural improvement over the hourly attempt,
not a guarantee of a specific number.

## Final real results (actual Colab runs, not estimates)

Two versions were fully trained and evaluated on the same real held-out test
set (20,955 windows, 25 districts, chronological split — never touched
during training or threshold tuning):

| Metric | 28-feature (deployed) | 35-feature (tested, not deployed) |
|---|---|---|
| Occurrence Accuracy | 0.774 | 0.769 |
| Occurrence Precision | 0.804 | 0.815 |
| Occurrence Recall | 0.917 | 0.889 |
| Occurrence F1 | 0.857 | 0.850 |
| Occurrence ROC-AUC | 0.813 | 0.801 |
| Occurrence Brier score | 0.162 | 0.165 |
| Amount R² (rain windows only) | 0.244 | 0.262 |
| Amount MAE (mm) | 6.056 | 5.948 |
| Combined R² | 0.278 | 0.292 |
| Combined MAE (mm) | 5.068 | 4.958 |

**Why the 28-feature version is what's actually deployed, despite the
35-feature version scoring marginally higher on R²/Amount metrics:** the 7
extra features (dew point, pressure, wind direction, vapour pressure
deficit, soil moisture) require live data from WeatherAPI at inference
time, in production, for every real forecast request. Pressure and wind
direction are available; dew point can be derived (see below); but
**`SoilMoisture_0_7cm` has no live source at all** — WeatherAPI doesn't
provide it, and there's no defensible formula to derive it from
temperature/humidity/rain the way apparent temperature can be. Serving a
model on a silently-approximated or missing input feature in production is
a real risk the ~0.01-0.02 R² gap doesn't justify — especially since that
gap is within the same magnitude as pure run-to-run training noise already
measured elsewhere in this project (two identical-config reruns swung by a
similar amount with zero code changes). The 28-feature model needs nothing
WeatherAPI doesn't already provide, directly or via a validated formula.

## What's now live in production (`Backend/`)

This model is deployed and serving real forecast requests, not just a
Colab artifact:

- **`Backend/models/rain24h_model.keras` / `rain24h_scaler.pkl`** — the
  28-feature model above. The scaler was regenerated locally rather than
  re-downloaded from Colab: the fit procedure is fully deterministic (fixed
  seed 42, same source data), verified to reproduce the exact same
  97,790/20,955/20,955 train/val/test split sizes as the original run.
- **`Backend/forecast/rain24h.py`** — the 28-feature engineering pipeline
  ported to run on live WeatherAPI data (not the offline Excel/Parquet
  dataset), plus:
  - `DISTRICT_CLIMATE_ZONE` and `ZONE_PEAK_MONTHS` — extracted directly
    from the real training data (not guessed); peak season turned out to
    be a clean function of (climate zone, month) per district, verified
    empirically, not assumed.
  - `apparent_temperature()` — the AU Bureau of Meteorology formula,
    bias-corrected against 5,000 real samples (raw MAE 0.986°C with a
    consistent bias; bias-corrected MAE 0.476°C, ~zero bias) — since
    WeatherAPI's hourly forecast/history objects were never confirmed to
    carry `feelslike_c` the way `current.json` does.
  - `classify_day_type()` — see "Day-type classifier" below.
- **`Rain24hRepository`** (`Backend/forecast/repositories.py`) — lazy-loads
  the model/scaler/calibration, mirroring the existing `ModelRepository`
  pattern. `compile=False` on load (the model's custom loss function isn't
  registered for Keras deserialization, and inference doesn't need it).
- **The hybrid: real 24h total, disaggregated into the hourly view.**
  `ForecastService._predict_24h_outlook()` runs the model and produces a
  point estimate, an occurrence probability, and an **asymmetric 80%
  prediction interval built from real held-out validation residuals**
  (percentiles of predicted-minus-actual, not a flat ±MAE band — the
  residual distribution is meaningfully skewed, matching the literature's
  own warning that squared-error metrics are distorted by rare heavy-rain
  misses). `ForecastService._assemble()` then disaggregates that daily
  total across the 24 individual hours by the analog's real hourly SHAPE
  (which clock hours typically get more rain, from the past 7 real days) —
  so the hourly breakdown and the daily total now agree by construction,
  closing a real inconsistency the old analog+WeatherAPI-blend-only hourly
  logic had. Falls back to the pre-existing analog+WeatherAPI blend if the
  24h model is unavailable — never a hard dependency.

### Day-type classifier

Combines `Temp_Trend_24h` + `Humidity_Trend_24h` (features the model
already computes) with the predicted rain range to classify the day into
RAINY / SUNNY / OVERCAST / HOT_HUMID_STORM_RISK / MILD — rain amount alone
can't distinguish "system passing through, trailing drizzle, temp/humidity
already falling" from "afternoon storm building, temp/humidity still
climbing," even at the same predicted mm.

**Post-deployment bug found and fixed:** the first version required all
three signals (temp direction, humidity direction, rain band) to match via
strict AND per category. Checked against the real training data, this put
**67% of all real days into MILD** — a narrow-intersection design flaw, not
a property of Sri Lanka's weather. A second, separate bug compounded it:
the rain-band thresholds (3mm/10mm) were copied from `hourly_advisory`'s
*hourly* cutoffs but applied to a *24h TOTAL*, which routinely exceeds 10mm
(the "high" band was over-triggering on ordinary rainy days). Both fixed by
(1) loosening the rule matching to OR-based combinations and (2)
recalibrating the rain bands against the real 24h-rolling-total
distribution (LOW ≤2mm ≈48th percentile, MODERATE ≤8mm ≈78th percentile).
Re-verified against the same real historical data: MILD 34%, SUNNY 34%,
OVERCAST 20%, RAINY 10%, STORM_RISK 2% — a genuinely differentiated split
instead of a near-constant default.

A related, pre-existing bug (not introduced by this model, but surfaced by
testing it) was found in `forecast/utils.py`'s `daily_summary()`: the
GOOD/CAUTION/AVOID travel advisory was computed purely from the single
worst hour's rain (`max(rains_high)`), completely ignoring `wet_hours` —
so a day with rain spread thin across 10+ hours (never spiking hard in any
single hour) could read GOOD, while a day with only 3-4 wet hours (one of
which briefly spiked) read CAUTION. Fixed: `wet_hours >= 8` now also forces
at least CAUTION, so a day soaked across a third of its hours can't read as
a clean GOOD regardless of peak intensity.

## Baseline comparison — classical ML (XGBoost), in progress

The GRU hurdle model above is a deep-learning sequence model. A fair
comparison needs a classical ML baseline trained on the *same* engineered
features (not raw sequences) to check whether the GRU's sequential
modeling is actually earning its complexity, or whether a gradient-boosted
tree gets similar skill more cheaply. See **`extra/output/XGBoost/`** —
three separate models (temperature, humidity, rainfall), each trained
independently on the same flattened feature set this package already
engineers.

| Metric | GRU (this package) | XGBoost (temperature) | XGBoost (humidity) | XGBoost (rainfall) |
|---|---|---|---|---|
| R² | 0.278 (Combined, 28-feat) | *pending* | *pending* | *pending* |
| MAE | 5.068mm | *pending* | *pending* | *pending* |
| RMSE | 12.435mm | *pending* | *pending* | *pending* |

Fill in once `extra/output/XGBoost/`'s training scripts have been run —
see that folder's own README for how.
