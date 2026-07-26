# alternate_models/ — candidate models to beat the current forecaster

Four different model architectures, each in its own folder, trained and
evaluated identically so their R²/MAE/RMSE numbers are directly comparable.
The goal: find something that beats `Backend/models/best_checkpoint.keras`
on real accuracy (not just vibes), then swap it in.

**Nothing in `Backend/` or `Frontend/` is touched by anything in here.**
This is a separate, self-contained experimentation area, a sibling to
`extra/`'s existing scripts. Deploying a winner into production is a
manual, deliberate step you take later — nothing here does it automatically.

## What's currently shipped, for context

`Backend/models/best_checkpoint.keras` is a 2-layer stacked GRU
(128 units → 64 units) → Dropout → `Dense(72)` → reshape to `(24, 3)`.
96,456 trainable parameters. Its weak point architecturally: the `Dense(72)`
head treats all 24 forecast hours as one flat regression — it has no way to
let its own hour-5 prediction inform hour-6. Every model below fixes that
one way or another, or takes an entirely different approach (trees).

| # | Folder | Architecture | Key idea |
|---|--------|-------------|----------|
| 1 | `01_gru_seq2seq` | Encoder GRU → decoder GRU (RepeatVector) → TimeDistributed Dense | The direct, minimal fix: a proper sequence decoder instead of a flat Dense head |
| 2 | `02_bidirectional_lstm` | Bidirectional stacked LSTM → LSTM decoder | Different cell (LSTM vs GRU) + the encoder reads history in both directions |
| 3 | `03_seq2seq_attention` | Encoder GRU → decoder GRU + Luong attention | Lets each forecast hour look back across all 168 context hours and weight them by relevance, instead of compressing everything into one fixed vector |
| 4 | `04_lightgbm_multioutput` | Gradient-boosted trees (LightGBM), 3 models (one per target) with `lead_hour` as a feature | No neural network at all — rich hand-engineered features (lags, rolling stats) instead. Trains on CPU in seconds |

## Your hardware, and what that means for which to run where

- **Local (i5 3rd gen, 16GB RAM, GTX 960 4GB):** `04_lightgbm_multioutput`
  runs great here — CPU-only, no GPU needed, trains in seconds to low
  minutes even on a few years of data. The GTX 960 is CUDA-capable but its
  compute capability (5.2) and 4GB VRAM are well below what modern
  TensorFlow/cuDNN builds target — expect the three deep models to fall
  back to CPU or run very slowly if you force GPU. Don't fight it; use
  Colab for those instead.
- **Google Colab (free tier, T4 GPU):** run `01_gru_seq2seq`,
  `02_bidirectional_lstm`, and `03_seq2seq_attention` here. All three
  finish in a few minutes per run on a T4 for a few years of data across
  ~25 districts. Colab's free session limits (disconnects after
  inactivity, ~12h hard cap) are not a concern at this model size.

You don't have to run all four anywhere in particular — this is just where
each is *comfortable*, not a hard requirement.

## Parameters carried over from the current production model

These aren't guesses — they're read directly from `Backend/core/config.py`
and `Backend/forecast/utils.py` so a trained model here can be a drop-in
replacement:

- `INPUT_WINDOW = 168` (hours of history the model reads)
- `TARGET_HORIZON = 24` (hours ahead it predicts)
- Base feature contract: `Temperature_C, Precipitation_mm, Humidity_%,
  CloudCover_%, WindSpeed_kmh, WindGusts_kmh, DaylightScore, Hour_sin,
  Hour_cos, Month_sin, Month_cos, Temp_Change_3h` (12 features, exact order)
  — models 01-03 use exactly this, so they could replace
  `best_checkpoint.keras` without touching `Backend/forecast/repositories.py`.
- Targets: `Temperature_C, Precipitation_mm, Humidity_%`

**Start/end training dates are NOT hardcoded anywhere** — every script reads
the date range straight out of whatever xlsx/csv you provide (printed at
load time: `Date range: ... to ...`) and derives train/val/test cutoffs from
that automatically (70% / 15% / 15%, chronological — see "Why chronological
splitting" below). When you hand over the real data, just point `--data` at
it; there's nothing to edit.

## Your data

Not provided yet — every script defaults to a small **synthetic** sample
(`data/synthetic_sample.xlsx`, made by `common/make_synthetic_data.py`) so
the whole pipeline can be smoke-tested before your real data arrives. It
has already been used to verify every train.py, run_forecast.py,
compare_with_openmeteo.py, and leaderboard.py run start-to-finish with zero
errors — but **its numbers mean nothing**; it's a smooth fake curve, not
real weather. Don't read into any R²/MAE you see from it.

When you provide your real xlsx, `common/data_prep.py` will auto-detect
column names (see `RAW_COLUMN_ALIASES` in `common/config.py`) — it
recognizes common variants like `temperature_2m`, `Temperature_C`,
`relativehumidity_2m`, `Humidity_%`, etc., so you likely won't need to
rename anything. Required columns: a datetime/time column, and
temperature/precipitation/humidity/cloud-cover/wind-speed/wind-gusts/
radiation. A `district`/`location` column is optional but **important** if
your file has multiple districts concatenated — without it, all rows are
treated as one continuous series, and windows could otherwise span two
different districts' data.

## End-to-end workflow

```bash
# 1. One-time setup (from alternate_models/, using the repo's existing venv)
../../venv/Scripts/python.exe -m pip install -r common/requirements.txt

# 2. (Optional, for a smoke test before your real data arrives)
cd common && ../../../venv/Scripts/python.exe make_synthetic_data.py && cd ..

# 3. Train whichever model(s) you want (see each folder's README for details)
cd 01_gru_seq2seq && ../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx && cd ..
cd 04_lightgbm_multioutput && ../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx && cd ..
# ...etc for 02, 03

# 4. Compare all trained models side by side
../../venv/Scripts/python.exe leaderboard.py

# 5. Sanity-check a specific model against Open-Meteo's live forecast
../../venv/Scripts/python.exe compare_with_openmeteo.py 04_lightgbm_multioutput --district Kandy

# 6. Run a specific model's forecast for a district, printed to terminal
../../venv/Scripts/python.exe run_forecast.py 01_gru_seq2seq --district Colombo
```

On Google Colab, replace `../../venv/Scripts/python.exe` with plain
`python`/`!python`, `!pip install -r common/requirements.txt`, and mount
Google Drive to persist `artifacts/` between sessions — see each model
folder's README for the exact Colab cell sequence.

## Files at this level

- `common/` — shared code every model folder imports: `config.py` (the
  contract above), `data_prep.py` (column resolution, feature engineering,
  windowing, chronological split), `scaling.py` (MinMaxScaler fit/inverse,
  same strategy as production), `metrics.py` (R²/MAE/RMSE reporting +
  plots), `inference.py` (loads any trained model uniformly), `live_fetch.py`
  (pulls live Open-Meteo data for run/compare scripts), `make_synthetic_data.py`.
- `run_forecast.py` — run any trained model against live data, print its forecast.
- `compare_with_openmeteo.py` — run any trained model against Open-Meteo's
  live forecast, save a comparison chart.
- `leaderboard.py` — compare every trained model's test-set metrics side by side.
- `data/` — put your xlsx here (or point `--data` anywhere).
- `01_gru_seq2seq/`, `02_bidirectional_lstm/`, `03_seq2seq_attention/`,
  `04_lightgbm_multioutput/` — one folder per candidate model, each with
  its own `train.py`, `model.py` (or `features_gbm.py` for LightGBM), and
  `README.md`.

## Why chronological splitting (not random)

Every model here splits train/val/test by TIME — the oldest ~70% of windows
train, the next ~15% validate, the newest ~15% test — never randomly. A
random split would let a training window whose 168h context overlaps a test
window's target hours leak information across the split, making the test
R² look better than the model would actually do on genuinely unseen future
data. This is worth knowing if you ever modify these scripts: don't
`shuffle=True` a time series split.

## Reading the R²/MAE/RMSE reports

Every `metrics.json` reports three things, and all three matter:
- **Overall** — R²/MAE/RMSE averaged across all 24 forecast hours. The
  headline number, but it can hide a model that's great at hour+1 and
  useless at hour+24.
- **Per-hour** (`per_hour_metrics.png`) — MAE at each of the 24 lead hours.
  A model that degrades gracefully (slowly rising MAE) is more trustworthy
  than one that's excellent at hour+1 and falls off a cliff by hour+6.
- **Per-target** — temperature/precipitation/humidity separately.
  Precipitation R² will likely look much worse than temperature's for any
  model here — that's normal (rain is zero-inflated and inherently harder
  to regress; see `extra/README.md`'s section on the rain zero-floor fix
  applied to the production model), not a sign of a bug.

## After you pick a winner

None of this auto-deploys. If a model here beats production convincingly
(check the leaderboard AND the per-hour chart, not just one R² number):
1. Copy its `artifacts/model.keras` (or the 3 `model_*.pkl` files) and
   scaler/feature-cols into `Backend/models/`.
2. If it's one of the three deep models (01-03) and uses only the base
   12-feature contract, it can likely replace `best_checkpoint.keras`
   directly — same input shape, same output shape.
3. If it's LightGBM, `Backend/forecast/repositories.py` and `services.py`
   would need new code to run 3 sklearn-style `.predict()` calls with the
   tabular feature builder instead of a single Keras `.predict()` — a
   bigger change, not a drop-in swap. Ask before doing this; it changes the
   production inference path.
4. Whichever you pick, re-run something like `extra/backtest.py`'s
   train/holdout discipline against real historical data before trusting
   it in production — a good `metrics.json` here is necessary, not
   sufficient, the same way the humidity/temperature bias-correction saga
   in `extra/README.md` already taught us not to trust a single comparison.
