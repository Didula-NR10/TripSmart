# 04_lightgbm_multioutput — gradient-boosted trees

No neural network at all. Three LightGBM models (one per target:
temperature, precipitation, humidity), each trained on rich hand-engineered
tabular features, with `lead_hour` as an input feature so one model per
target covers all 24 forecast hours instead of needing 72 tiny models.

**This is the one to run on your own PC — no GPU needed, no Colab needed.**

## Why this approach, and why it might actually win

A GRU/LSTM has to learn temporal patterns (lags, trends, diurnal cycles)
implicitly from raw sequences. A tree model has no memory at all — so
instead, `features_gbm.py` computes those patterns explicitly as input
features: lag values at 24h and 168h back (same hour yesterday / last
week), rolling mean/std over the last 24h, rolling rain sums over 24h/72h,
cyclical hour/month encodings, and the momentum feature (`Temp_Change_3h`)
production also uses. Given good features, gradient-boosted trees are
frequently competitive with, or better than, small deep learning models on
this kind of moderately-sized weather data — and they train from scratch in
seconds to low minutes on a CPU, full stop.

Trade-off: no attention, no learned temporal representation — if there's a
complex pattern the hand-engineered features don't capture, a GBM can't
discover it the way a neural net might. But given the modest training data
size this project is likely to have (a few years, not millions of rows),
that's a very reasonable trade — see `../README.md`'s note that a good
`metrics.json` here isn't automatically "worse just because it's not deep
learning."

## The core design choice: long format, `lead_hour` as a feature

Rather than 72 separate models (one per target × lead-hour, each starved of
training data) or trying to force one model to output 72 values at once
(which LightGBM doesn't support natively), every origin hour is expanded
into 24 rows — one per lead hour — with `lead_hour`, `lead_hour_sin/cos`,
and the KNOWN calendar time of the hour being forecast (`target_hour_sin/cos`,
`target_month_sin/cos`) added as features. One model per target then learns
across all lead hours at once, pooling 24x more rows than a
one-model-per-hour approach would have. See `features_gbm.py` for the full
reasoning and the (fully vectorized — no slow Python loops) implementation.

## Steps — local (this is the one meant to run on your PC)

```bash
cd extra/alternate_models/04_lightgbm_multioutput

# smoke test first (optional but recommended) — this finishes in seconds
cd ../common && ../../../venv/Scripts/python.exe make_synthetic_data.py && cd ../04_lightgbm_multioutput
../../../venv/Scripts/python.exe train.py --n_estimators 100

# real training run, once you have your xlsx
../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx
```

Expect a real run (a few years of hourly data across ~25 districts) to
still finish in well under a few minutes on your hardware — this doesn't
need Colab, but you can run it there too if it's more convenient (no GPU
needed either way).

## Parameters

```
--data                    path to xlsx/csv (default: the synthetic smoke-test sample)
--sheet                   sheet name, if the xlsx has multiple (default: first sheet)
--n_estimators            max trees per model (default 800) — early stopping usually stops well before this
--learning_rate           default 0.05 — lower is more accurate but slower/needs more trees
--num_leaves              default 63 — higher can fit more complex patterns but risks overfitting on less data
--early_stopping_rounds   rounds without val improvement before stopping (default 50)
```

## Outputs (`./artifacts/`)

- `model_temperature.pkl`, `model_precipitation.pkl`, `model_humidity.pkl`
  — one LightGBM model per target, loadable with `joblib.load()`
- `tabular_feature_cols.json` — the origin-level feature list (before
  `lead_hour` etc. are added) each model expects at inference
- `metrics.json` — same R²/MAE/RMSE format as the deep models, directly comparable
- `per_hour_metrics.png`, `sample_predictions.png` — same as the deep models
- `feature_importance.png` — top-10 most-used features per target. Worth a
  look even before checking the leaderboard: if `lead_hour` or a lag
  feature dominates in a way that seems too strong, or a feature you'd
  expect to matter (e.g. `CloudCover_%` for humidity) barely registers,
  that's a useful diagnostic on the feature set itself, not just the model.

## After training

```bash
# from alternate_models/
python run_forecast.py 04_lightgbm_multioutput --district Colombo
python compare_with_openmeteo.py 04_lightgbm_multioutput --district Kandy
python leaderboard.py   # compare against the 3 deep models, once trained
```
