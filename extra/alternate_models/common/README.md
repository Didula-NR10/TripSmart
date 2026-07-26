# common/ — shared code, not run directly

Every model folder (`01_gru_seq2seq`, `02_bidirectional_lstm`,
`03_seq2seq_attention`, `04_lightgbm_multioutput`) imports from here so all
four are trained and evaluated identically — same feature engineering, same
train/val/test split, same metrics format. You don't run anything in this
folder directly, except optionally `make_synthetic_data.py` for a smoke
test. See `../README.md` for the full workflow.

## Files

- **`config.py`** — the shared contract: `INPUT_WINDOW=168`,
  `TARGET_HORIZON=24`, the 12-feature base contract (matches
  `Backend/forecast/utils.py` exactly), the optional extended feature set
  (lags/rolling stats, for LightGBM), target columns, chronological
  train/val/test fractions (70/15/15), and `RAW_COLUMN_ALIASES` — the list
  of column-name variants each raw field is recognized under, so your xlsx
  likely doesn't need any renaming.

- **`data_prep.py`** — `load_raw_table()` (reads xlsx/csv, resolves column
  names, sorts, dedupes), `engineer_features()` (base 12 + optional
  extended features, computed **per district** so lag/rolling features
  never leak across a district boundary), `make_windows()` (builds the
  `(168, 12) -> (24, 3)` sliding windows, also per-district-safe),
  `chronological_split()` (time-ordered 70/15/15 split — see "why
  chronological" in the top-level README).

- **`scaling.py`** — fits ONE `MinMaxScaler` on the training split's
  features only (never val/test — that would leak distribution info),
  used both to scale model inputs and to inverse-transform predictions
  back to real units. Same strategy as `Backend/models/scaler.pkl`.

- **`metrics.py`** — `regression_report()` computes R²/MAE/RMSE overall,
  per-target, and per-lead-hour; `print_report()`/`save_report()`; plotting
  helpers for training curves, per-hour MAE, and sample predicted-vs-actual
  windows. Every model folder's `train.py` calls these, so all four
  produce directly comparable `metrics.json` files.

- **`inference.py`** — `load_trained_model()` figures out whether a given
  `artifacts/` folder holds a Keras model or the LightGBM 3-model trio, and
  `predict_next_24h()` runs either uniformly. Used by `../run_forecast.py`
  and `../compare_with_openmeteo.py`.

- **`live_fetch.py`** — pulls a live context window (and, for the compare
  script, Open-Meteo's own forecast) directly from Open-Meteo. Separate
  from `../../model_pipeline.py` (production's version) because
  LightGBM's lag-168h feature needs more history than production's fixed
  7-day fetch to get a real (non-backfilled) value.

- **`make_synthetic_data.py`** — generates a small, plausible-looking fake
  hourly dataset (two districts, 70 days) so every train.py can be smoke
  tested before your real xlsx arrives. **Not real data** — don't read
  anything into the R²/MAE it produces; its only job is proving the code
  runs without errors.

## If you add a 5th field to your data (e.g. UV index)

1. Add its column-name aliases to `RAW_COLUMN_ALIASES` in `config.py`.
2. Add it to `OPTIONAL_RAW_COLUMNS` if it's not always present.
3. If you want deep models (01-03) to use it, add it to `BASE_FEATURE_COLS`
   — but note this breaks drop-in compatibility with the production 12-feature
   model (it expects exactly those 12, in that order).
4. If you only want LightGBM to use it, add it to `EXTENDED_FEATURE_COLS`
   in `config.py`, and compute it in `engineer_features()` in `data_prep.py`
   (under the `if extended:` branch).
5. Also add its live-fetch field name to `common/live_fetch.py`'s
   `HOURLY_FIELDS`/dataframe construction so live inference doesn't fail
   for want of it (this exact bug happened during testing — see
   `../README.md`'s note about `Pressure_hPa`/`DewPoint_C`).
