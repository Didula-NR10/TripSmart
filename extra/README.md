# extra/ — standalone model runner

A self-contained copy of the TripSmart GRU weather forecaster, pulled out of
`Backend/forecast/` so it can run on its own in a terminal — its own output,
completely separate from the FastAPI backend and the Expo frontend. Nothing
in `Backend/` or `Frontend/` is touched by anything in here (except that two
of the accuracy fixes below were also applied to `Backend/forecast/utils.py`
directly, since that's the live model).

Has its own copy of the trained model (`models/best_checkpoint.keras`,
`models/scaler.pkl`) and its own copy of the inference pipeline
(`model_pipeline.py`). Talks straight to Open-Meteo's free API — no backend
server, no database, no auth needed.

## 1. Setup (do this once)

This project already has a Python venv at the repo root (`../venv`) with
everything installed (tensorflow, pandas, etc.) except `matplotlib`. Easiest
path — from inside `extra/`:

```bash
../venv/Scripts/python.exe -m pip install matplotlib
```

Then run scripts with that same interpreter, e.g.:

```bash
../venv/Scripts/python.exe run_forecast.py Colombo
```

If you'd rather have a separate environment just for this folder:

```bash
cd extra
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

and then just `python run_forecast.py ...` as normal.

All commands below assume you're running from inside the `extra/` folder.

## 2. The files, and how to run each one

### `run_forecast.py` — run the model, print a forecast

```bash
python run_forecast.py                # Colombo by default
python run_forecast.py Kandy
python run_forecast.py NuwaraEliya    # any district name from DISTRICT_COORDS in model_pipeline.py
```

What it does: fetches the last 168 hours of real observations for the
district from Open-Meteo, runs the GRU model, prints the next 24 hours
(temperature, rain, humidity) as a table in the terminal. No files written.

### `compare_with_openmeteo.py` — model vs Open-Meteo's own forecast, with charts

```bash
python compare_with_openmeteo.py
python compare_with_openmeteo.py Kandy
```

What it does: fetches one window covering both the past (model input) and
the next 24 hours (Open-Meteo's own forecast for those same hours), runs the
model, lines both up by timestamp, prints a mean-absolute-difference summary
per metric plus a full hour-by-hour table, and saves a 3-panel chart
(temperature / precipitation / humidity, model vs Open-Meteo) to
`output/compare_<district>.png`.

Note: this checks agreement with Open-Meteo's *forecast*, which hasn't
happened yet either — good for a quick sanity check, not a real accuracy
measurement. Use `backtest.py` for that.

### `compute_bias_correction.py` — quick first-pass bias check (reference only)

```bash
python compute_bias_correction.py
```

What it does: runs the model against all 25 districts at once, compares each
against Open-Meteo's forecast, averages the error per lead hour, and prints
a candidate bias-correction table. This was the first attempt at fixing the
model's accuracy — it's kept for reference, but its results turned out to be
unreliable (see below) and were superseded by `backtest.py`. Takes a few
minutes (25 districts, 1 request/sec to be polite to Open-Meteo). Saves raw
numbers to `output/bias_residuals_temp.csv` / `bias_residuals_humidity.csv`.

### `backtest.py` — the real accuracy test, one district

```bash
python backtest.py                    # Colombo, 40 days back, every 6 hours
python backtest.py Kandy 60 4         # district, days_back, step_hours
```

What it does: pulls real historical weather from Open-Meteo's **archive**
(actual recorded conditions, not a forecast) for the given district, then
slides through it — at every origin timestamp it feeds the model the
preceding 168 real hours (same as production) and checks the 24h prediction
against what really happened next. It fits any bias correction on the first
~70% of origins (chronologically) and reports accuracy on the untouched last
~30%, so the numbers are honest, not just curve-fit. Prints MAE for
temperature/humidity/rain (raw vs corrected), plus a ready-to-paste
correction table. Saves per-origin results to `output/backtest_<district>.csv`.

Re-run this for a single district any time you want to sanity-check the
model, or a proposed fix, for just that district.

### `backtest_all_districts.py` — the real accuracy test, all 25 districts (recommended)

```bash
python backtest_all_districts.py              # all 25, 40 days back, every 6 hours
python backtest_all_districts.py 30 8         # days_back, step_hours
```

What it does: runs `backtest.py`'s exact holdout method separately for every
one of the 25 districts (climate varies a lot across Sri Lanka — coastal vs
hill-country vs dry-zone — so a correction fitted on one district doesn't
necessarily transfer to another). For each district it only keeps a
temperature/humidity correction if it actually beats the raw model on that
district's own held-out data; otherwise that district falls back to no
correction. Takes a while — 25 districts × ~165 origins each, likely
20–40 minutes. Saves progress incrementally to
`output/backtest_all_summary.csv` and `output/backtest_all_results.json`
(so a mid-run failure doesn't lose earlier districts), and at the end prints
the final `TEMP_BIAS_CORRECTION_C` / `HUMIDITY_BIAS_CORRECTION_PCT` dicts
ready to paste into `model_pipeline.py` and `Backend/forecast/utils.py`.

This is what was used to produce the tables currently shipped — see below.

### `model_pipeline.py` — not run directly

The shared engine all the scripts above import: feature engineering,
scaling, model inference, inverse-scaling, Open-Meteo fetch (both the live
forecast and the historical archive), the rain zero-floor, and the
per-district bias correction tables. Mirrors `Backend/forecast/utils.py` +
`Backend/forecast/repositories.py` exactly. You don't run this one yourself.

## 3. Accuracy fixes already applied (2026-07-26)

Baked into both this copy and the real backend (`Backend/forecast/utils.py`),
validated with `backtest_all_districts.py`'s per-district train/holdout
method against real historical weather (165 origins, 48 days, per district):

- **Rain zero-floor** — the model, trained with MSE on zero-inflated rain
  data, never predicted an exact 0 on dry hours (it hovered at 0.13–0.4mm).
  Predictions at or below `RAIN_ZERO_FLOOR_MM = 0.3` now snap to 0. One fixed
  threshold, applied to all districts (validated on Colombo: MAE 0.195mm raw
  → 0.163mm floored).
- **Per-district temperature & humidity bias correction** — each of the 25
  districts was backtested independently; a district only gets a correction
  if it beats the raw model on that district's own held-out data.
  **19/25 districts get a temperature correction, 21/25 get a humidity
  correction.** The other districts (e.g. Colombo's temperature: raw 0.37°C
  MAE beats corrected 0.40°C) are *intentionally* left at zero — that's a
  measured result, not a district that was skipped. See
  `output/backtest_all_summary.csv` for the full per-district before/after
  numbers.

Earlier, less rigorous attempts along the way (kept for reference, both
superseded):
- A single-snapshot comparison against Open-Meteo's own *forecast*
  (`compute_bias_correction.py`) suggested one shared correction table for
  all districts. It looked promising but didn't hold up against real ground
  truth — an early sign that "agrees with Open-Meteo's forecast" isn't the
  same as "accurate."
- Applying that one table to every district uniformly, before it was clear
  that per-district behavior differs enough to need separate tables.

## 4. Keeping this in sync

If the model is retrained, copy the new `best_checkpoint.keras` and
`scaler.pkl` into `extra/models/` to update this copy. If the feature
contract in `Backend/forecast/utils.py` ever changes, mirror the change in
`model_pipeline.py`'s `engineer_features` / `FINAL_FEATURE_COLS`.
