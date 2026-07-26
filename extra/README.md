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

### `backtest.py` — the real accuracy test (recommended)

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

This is what to re-run any time you want to know if the model — or a
proposed fix — is actually working, and it's what should be used before
trusting any new correction table.

### `model_pipeline.py` — not run directly

The shared engine all the scripts above import: feature engineering,
scaling, model inference, inverse-scaling, Open-Meteo fetch (both the live
forecast and the historical archive), the rain zero-floor, and the bias
correction table. Mirrors `Backend/forecast/utils.py` +
`Backend/forecast/repositories.py` exactly. You don't run this one yourself.

## 3. Accuracy fixes already applied (2026-07-26)

Two fixes are baked into both this copy and the real backend
(`Backend/forecast/utils.py`), validated with `backtest.py`'s train/holdout
method against real historical weather:

- **Rain zero-floor** — the model, trained with MSE on zero-inflated rain
  data, never predicted an exact 0 on dry hours (it hovered at 0.13–0.4mm).
  Predictions at or below `RAIN_ZERO_FLOOR_MM = 0.3` now snap to 0.
  Backtested MAE: 0.195mm raw → 0.163mm floored.
- **Humidity bias correction** — a genuine, generalizing per-lead-hour bias
  (`HUMIDITY_BIAS_CORRECTION_PCT`). Backtested holdout MAE: 3.69% raw →
  3.08% corrected. Derived from Colombo's backtest and applied to all 25
  districts (not district-specific).
- **Temperature bias correction was tried and rejected** — the first-pass
  table (`compute_bias_correction.py`, compared against Open-Meteo's
  forecast) looked like an improvement, but `backtest.py`'s holdout
  validation against real ground truth showed the raw, uncorrected model
  wins (0.37°C MAE raw vs 0.72°C with that correction). So
  `TEMP_BIAS_CORRECTION_C` is intentionally left at all zeros.

Both corrections currently apply the same numbers to all 25 districts (fit
on Colombo only). Run `backtest.py` per-district if you want district-specific
tuning instead.

## 4. Keeping this in sync

If the model is retrained, copy the new `best_checkpoint.keras` and
`scaler.pkl` into `extra/models/` to update this copy. If the feature
contract in `Backend/forecast/utils.py` ever changes, mirror the change in
`model_pipeline.py`'s `engineer_features` / `FINAL_FEATURE_COLS`.
