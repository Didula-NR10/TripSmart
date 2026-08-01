# TripSmart — Weather Forecasting System Documentation

**A technical reference for the GRU-based weather forecasting subsystem, the backend and frontend that serve it, and the research tooling built around it.**

Prepared: 2026-07-31 · Sri Lanka travel-planning application

Every fact in this document that describes *this* codebase was verified directly against the source files and the trained model artifacts (loaded and inspected at documentation time) rather than written from memory — file paths and line references are given throughout so each claim can be checked. Where a detail (e.g. the exact original training run's epoch count) is genuinely not recoverable from this repository, that is stated explicitly rather than guessed at. See §12 for the full list of such caveats.

---

## Table of Contents

1. [Introduction & Problem Statement](#1-introduction--problem-statement)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Data Pipeline](#3-data-pipeline)
4. [The GRU Model — Architecture Deep Dive](#4-the-gru-model--architecture-deep-dive)
5. [Post-Processing — Why Raw Model Output Is Never Served Directly](#5-post-processing--why-raw-model-output-is-never-served-directly)
6. [Backend Serving Architecture](#6-backend-serving-architecture)
7. [Frontend Application](#7-frontend-application)
8. [Evaluation & Backtesting Methodology](#8-evaluation--backtesting-methodology)
9. [Research Tooling (`extra/`)](#9-research-tooling-extra)
10. [Alternate Model Architectures Explored](#10-alternate-model-architectures-explored)
11. [Literature Review](#11-literature-review)
12. [Limitations & Honest Caveats](#12-limitations--honest-caveats)
13. [Future Work](#13-future-work)
14. [References](#14-references)

---

## 1. Introduction & Problem Statement

TripSmart is a travel-planning application for Sri Lanka. Its core differentiator over a generic weather app is that every forecast is filtered through a **travel advisory lens** — a traveler deciding whether to hike Ella Rock tomorrow doesn't want a temperature number, they want a GOOD / CAUTION / AVOID call for a specific district, a specific window of hours, backed by a number they can still see if they want it.

Sri Lanka's climate is a genuinely hard forecasting target for a small, self-trained model:

- **Two monsoon systems** (the south-west monsoon, roughly May–September, and the north-east monsoon, roughly December–February) drive opposite rainfall patterns on opposite sides of the island in the same calendar week.
- **Strong micro-climates** — the central highlands (Nuwara Eliya, Badulla) are 5–10°C cooler than the coastal lowlands 50km away, and convective afternoon showers in the wet zone are highly localized.
- **Zero-inflated rainfall** — most hours, in most districts, have exactly 0.0mm of rain. The distribution is a spike at zero plus a long right tail, not a smooth bell curve — this single fact shapes several design decisions described in §5.

The system's job is to take the last 168 hours (7 days) of recorded weather for a district and predict the next 24 hours of temperature, precipitation, and humidity — then turn those numbers into a decision a traveler can act on without needing to interpret raw meteorology themselves.

---

## 2. System Architecture Overview

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│   Frontend (Expo / RN)  │  HTTP  │        Backend (FastAPI)       │
│   React 19, Expo Router │◄──────►│                                │
│   Frontend/app/*.tsx    │        │  auth · forecast · notes ·     │
└─────────────────────────┘        │  journal · reports routers     │
                                    │                                │
                                    │  forecast/                     │
                                    │   ├─ routers.py   (HTTP)       │
                                    │   ├─ services.py  (pipeline)   │
                                    │   ├─ repositories.py (I/O)     │
                                    │   └─ utils.py (pure functions) │
                                    └───────────┬────────────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        ▼                       ▼                       ▼
              ┌──────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
              │  GRU model +      │   │  WeatherAPI.com       │   │  Supabase          │
              │  MinMaxScaler     │   │  (live 168h context +  │   │  (Postgres)         │
              │  (.keras + .pkl)  │   │  own forecast, keyed)  │   │  districts,          │
              │  Backend/models/  │   └─────────────────────┘   │  weather_observations,│
              └──────────────────┘                              │  forecast_runs, users │
                                                                  └──────────────────┘
```

A separate, self-contained copy of the inference pipeline lives in `extra/` (`extra/model_pipeline.py`), used for research, backtesting, and the comparison/verification scripts described in §9. It talks to **Open-Meteo** (a different, keyless upstream) rather than WeatherAPI.com, and is not wired into the live app at all — nothing in `Backend/` or `Frontend/` imports from `extra/`.

**Why two different upstream weather providers?** This is documented directly in the code (`Backend/core/config.py:51-55`):

> *"Open-Meteo's free tier is keyless and shared across every caller on a host's egress IP, which is exactly what made it 429 [rate-limited] under Hugging Face Spaces' shared IPs. WeatherAPI.com requires a key but keys are per-account, so this app's quota is no longer shared with strangers."*

In other words: the production backend switched to WeatherAPI.com because Open-Meteo's free tier is IP-pooled and got exhausted by other tenants on the same hosting platform, not because of any accuracy difference. The `extra/` tooling still uses Open-Meteo because it runs locally (one IP, not shared) and Open-Meteo additionally exposes a **historical archive API** (real recorded weather going back years) that WeatherAPI.com's free tier doesn't — which the backtesting tooling in §8 depends on.

---

## 3. Data Pipeline

### 3.1 Geographic scope

The model serves **25 districts** — every administrative district of Sri Lanka. Each is represented by a single latitude/longitude centroid (`Backend/forecast/utils.py:22-48`, mirrored in `extra/model_pipeline.py:44-70`):

| District | Lat | Lon | District | Lat | Lon |
|---|---|---|---|---|---|
| Colombo | 6.9271 | 79.8612 | Kurunegala | 7.4867 | 80.3647 |
| Gampaha | 7.0873 | 79.9997 | Puttalam | 8.0362 | 79.8283 |
| Kalutara | 6.5854 | 79.9607 | Anuradhapura | 8.3114 | 80.4037 |
| Kandy | 7.2906 | 80.6337 | Polonnaruwa | 7.9403 | 81.0188 |
| Matale | 7.4675 | 80.6234 | Badulla | 6.9934 | 81.0550 |
| Nuwara Eliya | 6.9497 | 80.7891 | Monaragala | 6.8728 | 81.3507 |
| Galle | 6.0535 | 80.2210 | Ratnapura | 6.6828 | 80.3992 |
| Matara | 5.9549 | 80.5550 | Kegalle | 7.2513 | 80.3464 |
| Hambantota | 6.1241 | 81.1185 | Jaffna | 9.6615 | 80.0255 |
| Kilinochchi | 9.3803 | 80.3770 | Mannar | 8.9810 | 79.9044 |
| Vavuniya | 8.7514 | 80.4971 | Mullaitivu | 9.2671 | 80.8128 |
| Batticaloa | 7.7170 | 81.7000 | Ampara | 7.2977 | 81.6724 |
| Trincomalee | 8.5874 | 81.2152 | | | |

A single model is shared across all 25 districts (it is not 25 separate models) — the district identity itself is not a model input feature. This is an important architectural fact: the model generalizes across climate zones purely from the *weather pattern* in its 168-hour input window, not from being told which district it's looking at. Per-district differences in accuracy (see §5.2 and §8) are corrected **after** the model runs, not baked into 25 separate networks.

### 3.2 Raw hourly fields collected

Both upstream providers are normalized to the same seven raw fields before feature engineering:

| Field | Description | Source (WeatherAPI.com) | Source (Open-Meteo) |
|---|---|---|---|
| `Temperature_C` | Air temperature, 2m | `temp_c` | `temperature_2m` |
| `Precipitation_mm` | Hourly rainfall | `precip_mm` | `precipitation` |
| `Humidity_%` | Relative humidity, 2m | `humidity` | `relativehumidity_2m` |
| `CloudCover_%` | Total cloud cover | `cloud` | `cloudcover` |
| `WindSpeed_kmh` | 10m wind speed | `wind_kph` | `windspeed_10m` |
| `WindGusts_kmh` | 10m wind gusts | `gust_kph` | `windgusts_10m` |
| `DaylightScore` | 0–1 solar proxy | derived from UV index | derived from `direct_radiation` |

**`DaylightScore` derivation differs by provider**, and this is worth understanding precisely because it's a real engineering compromise, not an oversight (`Backend/forecast/repositories.py:92-98`):

- **Open-Meteo path** (`extra/model_pipeline.py:276`): `DaylightScore = direct_radiation / 1000.0`, clipped to `[0, 1]` — a genuine solar irradiance reading in W/m², normalized against 1000 W/m² (a realistic peak for direct sun in the tropics).
- **WeatherAPI.com path** (`Backend/forecast/repositories.py:98,219`): WeatherAPI's free/standard plans don't expose solar irradiance at all, so `DaylightScore` is approximated as `uv_index / 11.0` while `is_day` is true, else `0.0`. UV index 11 ("extreme") is a realistic tropical midday peak in Sri Lanka, chosen as a stand-in ceiling so the resulting 0–1 signal has roughly the same shape as the original irradiance-based one, without inventing a fake W/m² number the provider never measured.

This is a deliberate proxy-for-a-proxy: the model was never trained to require *exact* solar irradiance, only a feature that rises through the morning, peaks near midday, and falls to zero at night — both derivations satisfy that shape even though their absolute scales come from physically different instruments.

### 3.3 Feature engineering — the 12-feature contract

Seven raw fields become **12 model features** (`Backend/forecast/utils.py:54-90`, byte-for-byte mirrored in `extra/model_pipeline.py:73-90`). The order is structural — the scaler and the model were both fit on this exact column order, and nothing may "sort" or "tidy" it:

```
1. Temperature_C      7.  DaylightScore
2. Precipitation_mm   8.  Hour_sin
3. Humidity_%          9.  Hour_cos
4. CloudCover_%       10.  Month_sin
5. WindSpeed_kmh      11.  Month_cos
6. WindGusts_kmh      12.  Temp_Change_3h
```

Five of these are engineered, not raw:

- **Cyclical hour/month encoding** (`Hour_sin/cos`, `Month_sin/cos`): a raw integer hour (0–23) implies hour 23 and hour 0 are 23 apart, when physically they're one hour apart — the model would have to learn that wraparound from scratch, wasting capacity. Encoding as `sin(2π·hour/24)` and `cos(2π·hour/24)` places every hour on a unit circle, so 23:00 and 00:00 sit next to each other in feature space exactly as they do on a clock. The same logic applies to month (December next to January).
- **`Temp_Change_3h`**: `Temperature_C.diff(periods=3).fillna(0.0)` — the temperature change over the preceding 3 hours, an atmospheric-momentum proxy (a temperature that's been falling fast for 3 hours behaves differently going forward than one that's been flat, even at the same absolute reading). The first 3 rows of any window have no prior context and are filled with `0.0`, exactly matching what happens at training time.

### 3.4 Scaling

All 12 features are scaled with **`sklearn.preprocessing.MinMaxScaler`**, feature range `[0, 1]`, fit once on the full training set and shipped as `Backend/models/scaler.pkl` (and its exact copy, `extra/models/scaler.pkl`).

Loading the actual shipped scaler and inspecting its fitted bounds gives real evidence of the data's observed range (verified at documentation time — these are the literal `data_min_`/`data_max_` arrays baked into the artifact):

| Feature | Observed min | Observed max |
|---|---|---|
| Temperature_C | 5.8 °C | 40.4 °C |
| Precipitation_mm | 0.0 mm | 85.4 mm |
| Humidity_% | 10 % | 100 % |
| CloudCover_% | 0 % | 100 % |
| WindSpeed_kmh | 0 | 76 |
| WindGusts_kmh | 0.7 | 115.9 |
| DaylightScore | 0 | 9 † |
| Hour_sin / Hour_cos | −1 | 1 |
| Month_sin / Month_cos | −1 | 1 |
| Temp_Change_3h | −13.1 °C | 13.2 °C |

† The DaylightScore column's fitted max of 9 (rather than 1) indicates the training data's raw radiation values were **not** pre-clipped to `[0,1]` the way the current `engineer_features` pipeline clips them before scaling — a small historical inconsistency between the exact numbers the scaler was originally fit on and the current feature code path. It has no practical effect (the scaler still maps live 0–1 DaylightScore values into a sensible low sub-range), but it's an example of the kind of artifact-vs-code drift that can accumulate in a project trained once and then evolved — flagged here rather than smoothed over.

A `MinMaxScaler` (rather than standardization/z-score) was used because it bounds every feature to a known range regardless of outliers, which matters for a `tanh`-gated recurrent network — GRU/LSTM internal gates saturate cleanly within `[0,1]`/`[-1,1]` ranges, and bounding inputs helps keep gradients well-behaved during training.

The temperature range (5.8–40.4°C) and humidity range (10–100%) are consistent with several years of Sri Lankan weather spanning both the cool highlands (Nuwara Eliya routinely drops toward single digits at night) and the hot dry zone (Anuradhapura/Hambantota regularly exceed 35°C).

### 3.5 Windowing and splitting

- **Input window**: 168 consecutive hours (exactly 7 days) of raw observations, feature-engineered and scaled.
- **Output horizon**: 24 hours ahead, 3 target channels (`Temperature_C`, `Precipitation_mm`, `Humidity_%` — a subset of the 12 input features; the model does not predict cloud cover, wind, etc.).
- **Splitting discipline**: every training and evaluation script in this project (both `extra/alternate_models/common/config.py:101-103` and `extra/backtest.py`) splits **chronologically** — the earliest ~70% of the timeline for training, the next ~15% for validation, the final ~15% (or, for backtesting, the most recent third) held out entirely. This is a hard rule in every script's own comments: *"NEVER split time series data randomly (it leaks the future into the training set through overlapping windows)."* A random split would let the model "see" hours adjacent to a test window during training, inflating apparent accuracy in a way that would not hold up on genuinely new data.

---

## 4. The GRU Model — Architecture Deep Dive

### 4.1 Why a recurrent network, and why GRU specifically

Weather is a **sequential, temporally-dependent** signal — tomorrow's temperature depends on today's trajectory, not just today's single reading. Three broad families of model can consume a 168-step sequence:

1. **Recurrent networks** (RNN / LSTM / GRU) — process the sequence step by step, carrying a hidden state forward. Natural fit for variable-length temporal dependency, but sequential computation is slower to train than a fully parallel architecture.
2. **Gradient-boosted trees** on a "flattened" feature table (lag features, rolling statistics) — no innate sequence modeling, but fast, robust to messy tabular data, and often extremely strong on structured environmental data (see §10.4 and §11.5).
3. **Transformers / attention-only architectures** — fully parallel, capture long-range dependency well, but need substantially more data and compute to train from scratch than a 25-district, single-country dataset of this size comfortably supports.

**GRU (Gated Recurrent Unit)**, introduced by Cho et al. (2014) [1], was chosen over the older **LSTM** (Hochreiter & Schmidhuber, 1997) [2] as the recurrent cell. A GRU merges LSTM's separate forget/input gates into a single **update gate**, and merges the cell state and hidden state into one vector:

```
z_t = σ(W_z · [h_{t-1}, x_t])                 (update gate)
r_t = σ(W_r · [h_{t-1}, x_t])                 (reset gate)
h̃_t = tanh(W · [r_t ⊙ h_{t-1}, x_t])          (candidate state)
h_t = (1 − z_t) ⊙ h_{t-1} + z_t ⊙ h̃_t         (new hidden state)
```

This gives GRU roughly 25% fewer parameters than an LSTM of the same hidden size (no separate cell state, one fewer gate), which matters directly for this project: less data is needed to fit the same effective capacity without overfitting, and training is faster on modest hardware (relevant given the free-tier Colab constraint this model was trained under — see §12). Chung et al. (2014) [3] benchmarked GRU against LSTM across several sequence tasks and found comparable performance with fewer parameters, which is the standard justification cited for preferring GRU on small-to-medium datasets — exactly this project's regime (25 districts, single-country, multi-year hourly data, not a global multi-decade reanalysis dataset).

### 4.2 The exact shipped architecture

The production model, `Backend/models/best_checkpoint.keras` (byte-identical copy at `extra/models/best_checkpoint.keras`), was loaded and its architecture inspected directly for this document. Its real, verified structure is:

```
Model: "TripSmart_GRU_Forecaster"
┌────────────────────────────┬──────────────────┬───────────┐
│ Layer (type)                │ Output Shape       │ Param #   │
├────────────────────────────┼──────────────────┼───────────┤
│ context_window (InputLayer) │ (None, 168, 12)    │ 0         │
│ gru_encoder_1 (GRU)          │ (None, 168, 128)   │ 54,528    │
│ dropout_1 (Dropout)          │ (None, 168, 128)   │ 0         │
│ gru_encoder_2 (GRU)           │ (None, 64)          │ 37,248    │
│ dropout_2 (Dropout)          │ (None, 64)          │ 0         │
│ dense_projection (Dense)      │ (None, 72)          │ 4,680     │
│ cast_to_fp32 (Activation)     │ (None, 72)          │ 0         │
│ forecast_output (Reshape)     │ (None, 24, 3)       │ 0         │
└────────────────────────────┴──────────────────┴───────────┘
Trainable params: 96,456
```

In prose:

1. **Input**: a `(168, 12)` tensor — one 7-day, 12-feature window.
2. **`gru_encoder_1`**, a GRU layer with **128 units**, `return_sequences=True` — it emits a hidden state for *every* one of the 168 timesteps, not just the last one, feeding a full sequence forward into the second GRU layer rather than compressing to a single vector too early.
3. **Dropout** (`dropout_1`) — regularization, randomly zeroing a fraction of activations during training to reduce overfitting on a comparatively small dataset.
4. **`gru_encoder_2`**, a second GRU layer with **64 units**, `return_sequences=False` (the default) — this one *does* compress the whole 168-step sequence down to a single 64-dimensional vector: a compact summary of "everything that mattered about the last 7 days," which is what feeds the prediction head.
5. **Dropout** (`dropout_2`) — a second regularization pass on the summary vector.
6. **`dense_projection`**, a fully-connected layer with **72 output units** — note `72 = 24 hours × 3 target channels`. This single dense layer directly produces every future value at once.
7. **`cast_to_fp32`** — a dtype-cast layer, present because this model was very likely trained with Keras **mixed-precision** (`mixed_float16`) enabled, where internal compute runs in float16 for speed/memory but outputs are cast back to float32 before loss computation — consistent with `forecast/services.py:78-80`'s comment that *"Mixed-precision training can push outputs a hair outside the scaler's fitted range; clip before inverting or the error is amplified"* (the clipping this comment describes is applied at inference time specifically to guard against this).
8. **`forecast_output`**, a `Reshape` from `(72,)` to `(24, 3)` — purely structural, turns the flat 72-vector back into "24 hours × 3 channels" for downstream code.

**Architecturally, this is a "direct multi-step" forecaster, not a sequence-to-sequence (encoder-decoder) model.** It does not generate hour 1, then feed hour 1 back in to generate hour 2, and so on (that pattern is called *autoregressive* or *recursive* multi-step forecasting, and is used instead in the *weekly outlook* feature at the day level — see §6.3 — but not within the 24-hour single-shot forecast). Instead, one forward pass produces all 24 hours × 3 channels simultaneously from the single 64-dimensional summary vector. This is a deliberate, well-established trade-off in time series forecasting (discussed further in §11.2): direct multi-step avoids **error accumulation** (a wrong hour-1 prediction poisoning every subsequent hour, as happens in autoregressive rollout), at the cost of not letting later hours condition on the model's own earlier predictions the way a true encoder-decoder can. §10.1 and §10.3 describe two alternative architectures built and smoke-tested specifically to explore the encoder-decoder / attention side of this trade-off, for comparison against the shipped direct-forecast design.

**Total parameter count**: 96,456 trainable weights (≈377 KB) — a genuinely small model by deep learning standards, appropriate for a single-country, 25-district dataset and for the free-tier hardware constraint it was trained under (see §12).

### 4.3 Loss function and training regime

The model was trained as a standard supervised regression problem:

- **Loss function**: Mean Squared Error (MSE) between predicted and true scaled values across all 24 hours × 3 channels. This is the conventional default for continuous-valued regression and is exactly what every training script mirrored in this repository (`extra/alternate_models/*/train.py`) also uses (e.g. `model.compile(optimizer=Adam(1e-3), loss="mse", metrics=["mae"])`).
- **Optimizer**: Adam — the near-universal default for training recurrent networks, combining per-parameter adaptive learning rates with momentum.
- **Regularization**: two Dropout layers (see §4.2) — the only regularization visible in the architecture itself; no L1/L2 weight decay is present in the saved graph.
- **Standard companion techniques used throughout this project's training scripts** (and virtually certain to have been used for the original checkpoint too, given the architecture's `dropout_1`/`dropout_2` naming convention and the general shape of the pipeline): `EarlyStopping` on validation loss with `restore_best_weights=True` (stop training once validation loss stops improving, and roll back to the best epoch rather than the last one), and `ReduceLROnPlateau` (halve the learning rate when validation loss plateaus, to allow finer convergence late in training).

**A significant, honestly-stated caveat**: the *exact* original training notebook or script that produced `best_checkpoint.keras` — including the precise epoch count, batch size, learning-rate schedule, exact training-data date range, and total row count — is **not stored in this repository**. Per earlier project context, the original model was trained in Google Colab's free tier; only the resulting artifacts (`best_checkpoint.keras`, `scaler.pkl`) were brought into this codebase, not the training notebook itself. Everything stated above about loss/optimizer/regularization is either (a) directly verifiable from the saved model graph (layer types, dropout presence, the mixed-precision cast layer), or (b) the training methodology **this project's own `extra/alternate_models/` scripts use**, which were deliberately built to mirror the same contract (168h→24h, same 12 features, same MinMaxScaler approach) as a reproducible stand-in. Where a fact is inferred rather than directly verified, this document says so rather than presenting a guess as measured fact.

### 4.4 Inference: turning 168 raw hours into 24 real-unit predictions

The full inference path, identical in `Backend/forecast/services.py:53-82` and `extra/model_pipeline.py:233-251`:

1. **`engineer_features(frame)`** — 168 raw rows → 12 engineered columns, in the fixed order (§3.3).
2. **NaN check** — any gap in the input window (missing hour) would have produced a `NaN` after `.diff()` or similar; the pipeline raises rather than silently feeding garbage to the model.
3. **`scaler.transform(...)`** — the fitted `MinMaxScaler` maps every column into `[0,1]` using the exact bounds in §3.4.
4. **Reshape to `(1, 168, 12)`** — Keras expects a batch dimension even for a single prediction.
5. **`model.predict(tensor)`** — one forward pass, producing a `(24, 3)` array of *scaled* predictions.
6. **`np.clip(raw, 0.0, 1.0)`** — mixed-precision rounding can push values a hair outside `[0,1]`; clip before inverting, since the scaler's inverse transform amplifies any out-of-range value.
7. **`inverse_transform_targets(...)`** — the tricky part. The `MinMaxScaler` was fit on **all 12 columns**, so `scaler.inverse_transform()` demands a 12-column input, but the model only predicts 3 of them. The code builds a `(24, 12)` zero matrix, slots the 3 predicted channels into their original column positions (indices 0, 1, 2 — `Temperature_C`, `Precipitation_mm`, `Humidity_%`), inverts the whole thing, then pulls those same 3 columns back out. The 9 unpredicted columns are mathematically irrelevant to this trick (each column's inverse transform is independent — `MinMaxScaler` has no cross-feature coupling), so filling them with zero is safe and produces the exact same 3 real-unit values as if the scaler had been fit on 3 columns alone.
8. **`clamp_physical(...)`** — see §5, the final and most consequential step.

---

## 5. Post-Processing — Why Raw Model Output Is Never Served Directly

This is, in practical terms, the single most important section of this document, because it directly determines what a user actually sees, and it is where this project's most substantial engineering effort (documented across many backtesting runs) went.

### 5.1 The zero-inflation / "phantom rain" problem

A regressor trained with MSE loss on a target that is exactly `0.0` most of the time (rain: dry hours vastly outnumber wet ones in Sri Lanka's hourly data) learns a specific, predictable failure mode: it converges toward predicting a small **positive constant** on dry hours rather than a true `0.0`. This happens because MSE penalizes being *confidently* wrong far more than being *vaguely* wrong — a model that always guesses a small positive number (say 0.15mm) accrues a smaller total squared error across a mixed dry/wet dataset than one that ever commits to an exact `0.0` and is occasionally very wrong on a wet hour. The result, observed directly in this project's own evaluation (`Backend/forecast/utils.py:108-112`): the raw model predicts roughly **0.13–0.4mm on hours that were, in reality, completely dry**.

**Fix**: `RAIN_ZERO_FLOOR_MM = 0.3` (`Backend/forecast/utils.py:113`, mirrored `extra/model_pipeline.py:151`) — any raw prediction at or below 0.3mm is snapped to exactly `0.0`. This trades a little sensitivity to genuine light drizzle (a real 0.2mm drizzle hour would also be floored to zero) for eliminating the much more common and much more misleading phantom-rain bias. Backtested on Colombo (`extra/README.md`, §3): raw MAE 0.195mm → floored MAE 0.163mm — a real, holdout-validated improvement, not a training-set artifact.

### 5.2 Per-district temperature & humidity bias correction

Beyond the rain floor, temperature and humidity predictions carry a **systematic, per-lead-hour bias** that differs by district — driven by Sri Lanka's real climate diversity (coastal vs. hill-country vs. dry-zone). The correction methodology went through two iterations, and it is worth documenting the failed first attempt because it illustrates a real methodological trap:

**Attempt 1 (superseded, kept only for reference — `extra/compute_bias_correction.py`)**: compared the GRU's predictions against Open-Meteo's own *forecast* (not real recorded weather) at a single point in time, across all 25 districts, and derived a bias table from the average discrepancy. This looked promising initially but **did not hold up** when re-tested at a different time of day — the "bias" it found was partly an artifact of comparing against a forecast (itself imperfect) at one specific hour, conflating "hours since the model was run" with "hour of day," since only one origin timestamp had been sampled.

**Attempt 2 (the one currently shipped — `extra/backtest.py` + `extra/backtest_all_districts.py`)**: the methodologically correct fix. For each district, the script:

1. Pulls real historical weather from Open-Meteo's **archive API** (ERA5-based reanalysis — actual recorded conditions, not a forecast) for a configurable lookback window (default 40 days).
2. Slides through it at a fixed step (default every 6 hours), and at each origin timestamp, feeds the model the preceding real 168 hours (exactly matching production) and records what it predicted for the next 24 hours.
3. Splits the resulting set of origins **chronologically**: the first ~70% fits a per-lead-hour bias table (mean error at lead-hour 1, lead-hour 2, ... lead-hour 24); the untouched final ~30% is used only to *evaluate* whether that correction actually helps.
4. **Keeps the correction only if it beats the raw (uncorrected) model on that district's own held-out data.** If it doesn't, the district is deliberately left at zero correction — not skipped, not a placeholder, a measured decision.

Run across all 25 districts (165 origins × 48 days per district, per `Backend/forecast/utils.py:129`), the result: **19 of 25 districts get a temperature correction; 21 of 25 get a humidity correction.** The other districts — notably Colombo's temperature channel, where the raw model's 0.37°C MAE beats the corrected 0.40°C — are intentionally left uncorrected because correction measurably hurt accuracy there on real held-out data.

The correction itself is additive and per-lead-hour: `TEMP_BIAS_CORRECTION_C[district][hour_index]`, a 24-element list (index 0 = one hour ahead, index 23 = 24 hours ahead) added directly to the raw predicted temperature before rounding; same structure for humidity. Both full tables — real numbers, not illustrative placeholders — are checked into `Backend/forecast/utils.py:136-209` and mirrored in `extra/model_pipeline.py`.

### 5.3 A critical nuance: production rain is not the GRU's own output at all

This is easy to miss by reading `clamp_physical()` in isolation, so it is stated plainly here: **the live backend's forecast endpoint does not use the GRU's rain channel at all.** `Backend/forecast/services.py:84-113` documents and implements this explicitly. The relevant excerpt from the code's own commentary:

> *"A GRU trained with MSE on a mostly-dry variable learns that predicting near-zero is usually 'safe' — it systematically underpredicts real light rain rather than being randomly noisy around it (proven: a real overnight test predicted flat 0.0mm for 8 straight hours while actual rain reached 1.3mm). No amount of retrying fixes a training-objective bias, so rain doesn't use the GRU's own regression output at all."*

Instead, the production API computes rain as an **[low, high] range** from two independent, non-GRU signals:

- **Analog**: the average recorded rainfall at that exact clock hour over the most recent 7 real days for that district (`_analog_rain_by_hour`) — "how much did it typically rain around 3pm this past week."
- **WeatherAPI's own forecast** for that specific valid hour, where available (an independently-trained third-party model's opinion, not this project's regressor).

The reported range is `[min(analog, weatherapi), max(analog, weatherapi)]`, and the travel advisory (§5.4) reacts to the **high** end of that range — "could reach up to X mm" should drive caution, not an average that might mask real risk.

This means: everything in §5.1 (the rain zero-floor) and the rain half of the backtesting in §8 describe the GRU's **own raw regression channel**, which is exactly what the research/comparison scripts in `extra/` (§9) exercise and chart — but it is *not* the code path a real user's forecast request in the live app actually goes through for rain. Temperature and humidity, by contrast, **do** come directly from the GRU (through `clamp_physical`, §5.2) in both the live backend and the `extra/` tooling — only rain has this special-cased hybrid path in production.

### 5.4 Physical clamping and the travel advisory

The final step, `clamp_physical()` (`Backend/forecast/utils.py:183-209`), enforces basic physical sanity a pure regressor has no innate concept of — nothing in an MSE loss stops the network from predicting −2mm of rain or 140% humidity:

- Temperature: rounded to 1 decimal place, no clamping (temperature has no hard physical bound the model would need protecting from within its trained range).
- Rain: floored at zero (`max(0.0, rain)`), and the zero-inflation floor from §5.1 applied.
- Humidity: clamped to `[0, 100]`, rounded to 1 decimal.

The resulting three numbers feed `hourly_advisory()` (`Backend/forecast/utils.py:221-231`), a simple, transparent decision table:

| Condition | Level | Reason |
|---|---|---|
| rain > 10.0mm | **AVOID** | Heavy rain |
| rain > 3.0mm | **CAUTION** | Light rain |
| humidity > 85% | **CAUTION** | Very humid |
| temperature > 35°C | **CAUTION** | Extreme heat |
| otherwise | **GOOD** | Clear conditions |

`daily_summary()` rolls 24 hourly advisories into one verdict for the day, using the **peak** hourly rain (not a daily cumulative total — the code's own reasoning, `Backend/forecast/utils.py:241-245`: *"24 individually-tiny hours can sum to a number that looks alarming despite no single hour ever feeling properly wet; the per-hour peak is the more honest 'how bad could the worst hour get' read."*).

---

## 6. Backend Serving Architecture

### 6.1 Stack

**FastAPI** (Python), with a layered structure per feature domain (`forecast/`, `auth/`, `notes/`, `reports/`), each split into `routers.py` (HTTP surface, thin), `services.py` (business logic/pipeline), `repositories.py` (I/O — upstream APIs, database, model artifacts), and `schemas.py` (Pydantic request/response models). `forecast/utils.py` is deliberately kept **pure** (no I/O, no FastAPI, no database) specifically so the exact same feature-engineering and post-processing code can be imported by the `extra/` research tooling without dragging in a live server or database connection.

### 6.2 API surface (`Backend/forecast/routers.py`)

All routes are under `/api/v1/forecast`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Is the model artifact present and loadable? |
| GET | `/districts` | The 25 districts the model serves, with coordinates |
| GET | `/current/{district}` | Live conditions right now, straight from WeatherAPI — no model involved |
| GET | `/weekly/{district}` | 7-day outlook (see §6.3) |
| GET | `/{district}` | The core 24-hour forecast, with advisories |
| POST | `/predict` | Bring-your-own 168-hour context (no live upstream fetch) |

`Backend/main.py` also registers routers for `auth` (signup/login/OTP email verification), `notes` and `journal` (the traveler's personal trip journal feature), and `reports`.

### 6.3 The weekly outlook: autoregressive rollout

Unlike the 24-hour forecast (§4.2's direct multi-step design), the **7-day outlook** (`Backend/forecast/services.py:241-372`) genuinely is autoregressive/recursive: day 1 is the standard single-shot 24h GRU forecast; for day 2 onward, the model's *own* predictions from the prior day are appended to the 168-hour input window (which slides forward, dropping the oldest 24 hours), and the model runs again on this now-partially-synthetic window.

Two details matter here:

- **Channels the model doesn't predict** (cloud cover, wind, wind gusts, daylight — 4 of the 12 input features) can't be extended this way, since the GRU has no opinion on them. They're filled with the past real week's average value at the same clock hour (`pattern = frame.groupby("Hour")[...].mean()`) — "the recent diurnal pattern of that exact district," a reasonable stand-in given none of these channels are being predicted anyway.
- **Confidence decays explicitly and is labeled, not hidden**: hours within the first 24 (day 1) are tagged `source="gru"`, `confidence="high"`; days reaching into 24–72 hours out are `"gru+pattern"`/`"medium"`; beyond 72 hours, `"gru+pattern"`/`"low"`. The code's own comment states the honest reasoning: *"Skill decays with distance: day 1 carries real-data momentum, later days increasingly reflect the model's own assumptions... instead of pretending day 6 is as trustworthy as tomorrow."*

### 6.4 Caching and resilience

- **`FORECAST_CACHE_MINUTES = 60`**: a completed model run is reused for an hour before re-running the GRU — upstream weather data itself only updates hourly, so re-running sooner produces an identical answer at CPU cost for nothing.
- **`WEATHERAPI_WINDOW_CACHE_MINUTES = 15`**: the raw fetched 168-hour observation window is shared across endpoints that both want "the last 168 hours for this district within moments of each other" (the 24h forecast and the weekly outlook), cutting real API call volume.
- **Retry with backoff**: upstream WeatherAPI.com calls retry on 429 (rate-limited) or 5xx responses, up to 3 attempts, doubling delay each time (`WEATHERAPI_RETRY_BASE_SECONDS = 1.5`), respecting a `Retry-After` header when present.
- **Graceful degradation, in two tiers**: if WeatherAPI is unreachable after retries, the service first tries to serve the last cached forecast *within the normal freshness window* (`get_fresh`); failing that, it serves the most recent forecast **regardless of age** (`get_stale`), explicitly marked `stale: true` with a reason in the payload, rather than returning a hard error. The code's own justification: *"the frontend's 'predict' button otherwise looks broken during a transient upstream rate limit."*
- **Idempotent observation writes**: every fetched window "tops up" the `weather_observations` table via a Postgres `ON CONFLICT DO NOTHING` upsert keyed on `(district_id, observed_at)` — overlapping windows across repeated calls never create duplicate rows.

### 6.5 Database schema (Supabase / Postgres, `Backend/core/models.py`)

Tables relevant to the forecasting subsystem:

- **`districts`** — the 25 seeded districts, name + lat/lon.
- **`weather_observations`** — one row per district-hour, the raw fields the feature pipeline needs (`uq_district_hour` unique constraint enforces one row per district per hour). This table is the growing historical record behind any future "almanac"/time-machine features.
- **`forecast_runs`** — a completed forecast payload (JSONB), timestamped by `forecast_origin`, indexed on `(district_id, forecast_origin)` for fast "most recent run" lookups — this is what backs the caching in §6.4.

(Other tables — `users`, `email_otps`, `auth_tokens`, `ground_reports`, `travel_journals`, `travel_notes` — support authentication and the trip-journal/ground-report features, not forecasting directly, and are out of scope for this document.)

Tables are created automatically by SQLAlchemy on server startup (`core.database.init_db`) — there is no SQL migration to run by hand.

---

## 7. Frontend Application

**Stack**: Expo SDK 54 (`~54.0.36`), Expo Router (`~6.0.23`) for file-based navigation, React 19.1.0, React Native 0.81.5.

Screens (`Frontend/app/*.tsx`): `index` (home), `explore`, `search`, `plan`, `trips`, `saved`, `journal`, `reports`, `profile`, laid out under a shared `_layout.tsx`. The forecast subsystem documented in this file is consumed by the app through `Frontend/lib/config.ts`'s `API_BASE_URL`, pointed at the FastAPI backend (either `localhost` for same-machine web/emulator testing, or the PC's LAN IP for a physical device on the same WiFi — see the comment block in that file for the exact reasoning).

---

## 8. Evaluation & Backtesting Methodology

### 8.1 Why a validation loss curve alone isn't trustworthy

A training run's validation loss tells you the model fits data from the same *distribution and time period* it was trained on. It does **not** tell you the model will still be accurate on a specific district, months later, against weather that has genuinely not happened yet — nor does it protect against the temporal-leakage trap described in §5.2's "Attempt 1." Real accuracy claims in this project are always backed by a **held-out chronological backtest against real recorded ground truth**, not a training-time metric.

### 8.2 Ground truth vs. forecast — a distinction this project treats carefully

Two Open-Meteo endpoints are used for two different, non-interchangeable purposes, and conflating them was an early mistake this project corrected:

- **`api.open-meteo.com/v1/forecast`** — a live *forecast*, including Open-Meteo's own prediction for hours that haven't happened yet. Useful for "do two forecasters agree with each other," **not** useful as ground truth, because it hasn't been checked against reality either.
- **`archive-api.open-meteo.com/v1/archive`** — ERA5-based reanalysis: **actual recorded conditions** for any past date range. This is the only source in this project treated as real ground truth.

`extra/backtest.py`'s methodology (§5.2 above) is built entirely on the archive endpoint for exactly this reason.

### 8.3 Backtest results summary

Per-district backtest (`extra/backtest_all_districts.py`, 165 origins × 48 days per district, chronological 70/30 fit/holdout):

- Rain zero-floor: MAE 0.195mm (raw) → 0.163mm (floored) on Colombo.
- Temperature correction improves holdout MAE in 19/25 districts; the remaining 6 (including Colombo) are intentionally left uncorrected because the raw model already wins there.
- Humidity correction improves holdout MAE in 21/25 districts.

Full per-district before/after numbers are saved to `extra/output/backtest_all_summary.csv` and `extra/output/backtest_all_results.json` by that script, and are regenerable at any time by re-running it.

---

## 9. Research Tooling (`extra/`)

A standalone copy of the inference pipeline plus a substantial suite of research and monitoring scripts, entirely separate from the live app (nothing in `Backend/` or `Frontend/` imports from `extra/`). Full usage instructions live in `extra/README.md`; summarized here for completeness:

| Script | Purpose |
|---|---|
| `model_pipeline.py` | The shared engine (not run directly) — feature engineering, scaling, inference, Open-Meteo fetch, rain floor, bias tables |
| `run_forecast.py` | Print a 24h forecast for a district to the terminal |
| `compare_with_openmeteo.py` | GRU vs. Open-Meteo's own *forecast*, charted — a quick sanity check, not an accuracy measurement |
| `compute_bias_correction.py` | The superseded first-pass bias attempt (§5.2), kept for reference |
| `backtest.py` | The real accuracy test for one district, against Open-Meteo's historical archive |
| `backtest_all_districts.py` | The same, run independently across all 25 districts — this produced the tables shipped in §5.2 |
| `plot_ground_truth_comparison.py` | GRU (raw and corrected) vs. real recorded weather, for a window that has already fully elapsed |
| `predict_8h.py` + `verify_predictions.py` | Two-step live tracking: log a GRU + Open-Meteo prediction now, verify both against reality once the hours have passed |
| `compare_three_way.py` | GRU vs. Open-Meteo vs. WeatherAPI.com, all three predictions for the same upcoming hours, charted side by side |

---

## 10. Alternate Model Architectures Explored

Four candidate architectures were built in `extra/alternate_models/`, each a complete, independently trainable pipeline (feature engineering, training script, evaluation/plotting, its own README), sharing the same 168h→24h, 12-feature (or optionally extended) contract so any of them is a drop-in replacement for the shipped checkpoint if retrained on real data and found to outperform it. All four were **smoke-tested end-to-end on synthetic data** (a generated stand-in dataset, since the real multi-year xlsx export had not yet been provided at the time these were built) to confirm every script runs error-free; the parameter counts and training times below are real, measured numbers from those smoke-test runs, not estimates — but the resulting *accuracy* numbers from a 1-epoch synthetic smoke test are not meaningful and are not reported here (only real training on real data would produce a meaningful R²/MAE comparison against the shipped model).

| Model | Architecture | Trainable params | Smoke-test train time |
|---|---|---|---|
| `01_gru_seq2seq` | Encoder GRU(128)→GRU(96, returns state)→RepeatVector(24)→decoder GRU(96, seeded with encoder state)→TimeDistributed Dense(3) | 184,995 | 31.2s |
| `02_bidirectional_lstm` | Bidirectional LSTM(96) ×2 → RepeatVector → LSTM(96) → TimeDistributed Dense | 416,931 | 52.3s |
| `03_seq2seq_attention` | Encoder GRU(128)→GRU(96, sequences+state)→decoder GRU(96)→Luong-style dot-product attention (`tf.keras.layers.Attention`)→Concatenate→Dense(64, ReLU)→Dense(3) | 188,035 | 31.6s |
| `04_lightgbm_multioutput` | Gradient-boosted trees, "long-format" table (lead-hour as an explicit feature, 24 rows per origin instead of 24 separate models) | 55,632 (leaves, not weights) | 4.6s |

- **`01_gru_seq2seq`** is the closest conceptual sibling to the shipped model, but implements a *true* encoder-decoder: the encoder's final hidden state seeds the decoder, which then generates the 24-hour sequence step by step (via `RepeatVector`, not autoregressive feedback of its own outputs) — directly testing whether letting the decoder condition each hour on the encoder's summary (rather than one flat Dense projection, §4.2) improves accuracy.
- **`02_bidirectional_lstm`** processes the 168-hour input in both time directions (forward and backward) before summarizing — in principle able to use "what came after" a given hour within the historical window to better characterize it, at roughly 4× the parameter count of the shipped model.
- **`03_seq2seq_attention`** adds a Luong-style attention mechanism (§11.3) on top of the seq2seq structure, letting each decoded hour selectively weight *which* of the 168 encoded input hours mattered most for that specific prediction, rather than compressing everything into one fixed-size summary vector the way the shipped model's single 64-unit GRU does.
- **`04_lightgbm_multioutput`** is architecturally unrelated to the other three — no recurrence at all. It reframes the sequence problem as a tabular regression: lag features and rolling statistics stand in for the GRU's learned temporal memory, and `lead_hour` (1–24) becomes an explicit input feature, so one model learns "what changes between predicting 1 hour out vs. 24 hours out" directly from data rather than needing 24 separate models or a decoder loop. Trains in a fraction of the time of any recurrent model and, on many structured/tabular environmental datasets, gradient-boosted trees are competitive with or superior to deep sequence models (§11.5) — worth testing empirically once real data is available, rather than assumed.

Each folder's own `README.md` gives exact run instructions, expected R²/MAE/RMSE reporting once trained on real data, and Google Colab-appropriate parameter guidance (the user's local hardware — an i5 3rd-gen CPU with a 4GB GTX 960 — cannot reasonably train any of these; all four are designed and documented for Colab's free-tier T4 GPU instead).

---

## 11. Literature Review

### 11.1 Recurrent neural networks for sequence modeling

The vanishing-gradient problem in vanilla RNNs — gradients shrinking exponentially as they backpropagate through many timesteps, making long-range dependencies practically unlearnable — was solved by **Long Short-Term Memory (LSTM)** networks (Hochreiter & Schmidhuber, 1997) [2], which introduced a separate cell state protected by input/forget/output gates, allowing gradients to flow largely unimpeded across long sequences. **GRU** (Cho et al., 2014) [1], originally introduced as part of an encoder-decoder architecture for statistical machine translation, simplified this design — merging the cell and hidden state and reducing to two gates — while retaining LSTM's core advantage over vanilla RNNs. Chung et al.'s (2014) empirical comparison [3] found GRU and LSTM broadly comparable in accuracy across several sequence-modeling benchmarks, with GRU's smaller parameter count giving it an edge on smaller datasets or constrained compute — directly relevant to this project's own choice (§4.1) given its comparatively small, single-country dataset and free-tier training hardware.

### 11.2 Sequence-to-sequence learning and multi-step forecasting strategies

Sutskever, Vinyals & Le (2014) [4] introduced the encoder-decoder ("seq2seq") framework — one recurrent network compresses an input sequence into a fixed-size vector, a second recurrent network decodes an output sequence from it — originally for machine translation, but the architecture generalized directly to multi-step time series forecasting (predict a sequence of future values from a sequence of past ones). The time series forecasting literature broadly recognizes three strategies for multi-step-ahead prediction: **recursive/autoregressive** (feed each prediction back in to generate the next, as this project's own weekly-outlook rollout does, §6.3), **direct** (train the model to output the entire future horizon in one shot, as the shipped 24-hour model does, §4.2), and **seq2seq/encoder-decoder** (a dedicated decoder conditioned on an encoded summary, as `extra/alternate_models/01_gru_seq2seq` implements). Direct strategies avoid the compounding-error problem inherent to recursive forecasting (an early mistake propagates and amplifies through every subsequent step) but cannot let later predictions explicitly condition on earlier ones the way a true decoder can — the exact trade-off discussed in §4.2, and the direct motivation for building and comparing the seq2seq alternative in §10.

### 11.3 Attention mechanisms

A pure encoder-decoder forces the entire input sequence through one fixed-size bottleneck vector, which degrades as input length grows — 168 hours is a substantial sequence to compress losslessly into 64 or 96 numbers. **Attention**, introduced by Bahdanau, Cho & Bengio (2015) [5] and simplified into several "global" variants (including the dot-product/multiplicative form used in this project's `03_seq2seq_attention`) by Luong, Pham & Manning (2015) [6], lets the decoder look back at *every* encoder timestep at each decoding step, learning to weight which input hours matter most for each specific output hour, rather than relying on one fixed summary. This directly motivated the third alternate architecture explored in §10.

### 11.4 Deep learning for weather forecasting and post-processing

Deep learning applied to weather has broadly followed two tracks: (a) end-to-end spatiotemporal forecasting from gridded reanalysis data (e.g. ConvLSTM-style and, more recently, graph/transformer-based global models), which require far larger datasets and compute than this project's scope, and (b) **statistical post-processing / Model Output Statistics (MOS)** — using a learned model to correct the systematic bias of an existing forecast or simpler predictive signal, a decades-old technique in operational meteorology (Glahn & Lowry, 1972 first formalized MOS for NWP output) [7], long predating deep learning and still standard practice at national weather services. The per-district, per-lead-hour bias correction in §5.2 is architecturally a MOS approach: rather than trying to make the primary model itself perfect, a lightweight, empirically-fit correction is layered on top of it, validated on genuinely held-out data — the same philosophy underlying operational MOS systems.

### 11.5 Gradient-boosted trees for structured/tabular sequence problems

Despite recurrent and transformer architectures dominating deep-learning-native sequence tasks (language, audio), **gradient-boosted decision tree ensembles** remain highly competitive on structured/tabular problems, including many time series forecasting benchmarks, once the sequence is reframed as a tabular regression via lag and rolling-window features. **LightGBM** (Ke et al., 2017) [8] — used in `extra/alternate_models/04_lightgbm_multioutput` — introduced gradient-based one-side sampling and exclusive feature bundling to make gradient boosting dramatically faster on large tabular datasets than earlier implementations (e.g. XGBoost, Chen & Guestrin 2016 [9]) while matching or exceeding their accuracy. For a dataset of this project's scale (25 districts × multi-year hourly data, a genuinely tabular/structured signal once lag/rolling features are engineered), tree ensembles are a legitimate, well-evidenced alternative to a recurrent network, and are dramatically cheaper to train (§10's measured 4.6s smoke-test time vs. 31–52s for the recurrent alternatives) — which is precisely why it was included as one of the four candidates rather than assumed inferior by default.

### 11.6 Zero-inflated regression for precipitation

Precipitation is a canonical example of a **zero-inflated** target in the statistics literature — a large point-mass at exactly zero, plus a continuous, right-skewed distribution for the non-zero values. Standard approaches include zero-inflated regression models (e.g. a two-part hurdle model: first predict "will it rain at all," then predict "how much, given that it does") and, in machine learning practice, simpler heuristic corrections like the thresholded floor used in this project (§5.1). The production backend's decision to bypass the GRU's rain channel entirely in favor of a historical-analog + third-party-forecast hybrid (§5.3) is, in effect, a pragmatic real-world response to exactly this well-documented difficulty: a single MSE-trained regressor is a poor natural fit for a zero-inflated target, and rather than building a full two-part hurdle model, this project substitutes two independently-sourced non-regression signals instead.

### 11.7 Numerical weather prediction context

The upstream data this project depends on ultimately traces back to conventional **Numerical Weather Prediction (NWP)** — physics-based atmospheric simulation, not machine learning. Open-Meteo's historical archive is built on **ERA5**, the European Centre for Medium-Range Weather Forecasts' (ECMWF) fifth-generation atmospheric reanalysis (Hersbach et al., 2020) [10], which combines historical observations with a physical model via data assimilation to produce a globally consistent, hourly, multi-decade record — this is what makes it usable as genuine "ground truth" for backtesting (§8.2), as distinct from any live forecast (including this project's own), which is inherently a prediction about the future and cannot itself serve as ground truth.

---

## 12. Limitations & Honest Caveats

Stated plainly, in one place, rather than scattered:

1. **The exact original training run for `best_checkpoint.keras` is not reproducible from this repository.** Only the trained artifacts (the `.keras` checkpoint and the fitted `.pkl` scaler) are checked in; the Colab notebook or script that produced them, including the precise epoch count, batch size, learning-rate schedule, and exact training-data date range/row count, is not present. Everything stated about its training regime in §4.3 is either directly verified from the saved model graph or is this project's own reconstructed/mirrored training methodology (`extra/alternate_models/`), not a verified transcript of the original run.
2. **Production rain predictions do not use the GRU at all** (§5.3) — this is a significant enough departure from "the model predicts weather" that it is called out twice in this document to avoid it being missed.
3. **The bias-correction tables (§5.2) are only as current as their last backtest run** (2026-07-26, per the code's own comment) — if the model is ever retrained, both tables must be regenerated (`extra/backtest_all_districts.py`), or they will silently correct a model that no longer has the same biases.
4. **A `DaylightScore` scaling inconsistency exists between the fitted scaler and the current feature code** (§3.4) — the scaler's fitted max (9) doesn't match the current pipeline's clipped `[0,1]` range for that column, a small drift from an earlier version of the feature code, with no observed practical impact but flagged for transparency.
5. **The four alternate model architectures (§10) are unvalidated on real data.** They were built and confirmed error-free via synthetic-data smoke tests only, at the time of this document — no real accuracy comparison against the shipped model yet exists, pending the real multi-year xlsx export.
6. **Backtesting depends on Open-Meteo's archive, not an independent third source.** Since the production model may itself have originally been trained on Open-Meteo-derived data, "ground truth" here is Open-Meteo's ERA5-based reanalysis specifically — an extremely credible source (it is what national weather services and the broader NWP research community treat as reference-quality reanalysis) but not literally a physical weather station reading independent of the entire Open-Meteo/ECMWF pipeline.

---

## 13. Future Work

- Train one or more of the four alternate architectures (§10) on real multi-year data once available, and compare R²/MAE/RMSE against the shipped model using the same chronological-holdout discipline as §8, not just training-time validation loss.
- Consider a proper two-part (hurdle) model for precipitation specifically, given the zero-inflation discussion in §11.6, rather than the current floor-based heuristic — potentially closing some of the gap that currently forces production to bypass the GRU's rain output entirely (§5.3).
- Re-run `backtest_all_districts.py` on a regular cadence (not just after a retrain) to catch bias drift as more real observation history accumulates in `weather_observations`.
- Extend the live prediction-vs-reality tracking (`predict_8h.py` / `verify_predictions.py`, §9) into a continuously accumulating, dashboarded track record, rather than one-off manual runs.
- Resolve the `DaylightScore` scaler/pipeline drift noted in §3.4 / §12.4 the next time the model is retrained.

---

## 14. References

[1] Cho, K., van Merriënboer, B., Gulcehre, C., Bahdanau, D., Bougares, F., Schwenk, H., & Bengio, Y. (2014). *Learning Phrase Representations using RNN Encoder-Decoder for Statistical Machine Translation.* Proceedings of EMNLP 2014. arXiv:1406.1078.

[2] Hochreiter, S., & Schmidhuber, J. (1997). *Long Short-Term Memory.* Neural Computation, 9(8), 1735–1780.

[3] Chung, J., Gulcehre, C., Cho, K., & Bengio, Y. (2014). *Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling.* NeurIPS 2014 Deep Learning Workshop. arXiv:1412.3555.

[4] Sutskever, I., Vinyals, O., & Le, Q. V. (2014). *Sequence to Sequence Learning with Neural Networks.* Advances in Neural Information Processing Systems (NeurIPS) 27.

[5] Bahdanau, D., Cho, K., & Bengio, Y. (2015). *Neural Machine Translation by Jointly Learning to Align and Translate.* International Conference on Learning Representations (ICLR) 2015. arXiv:1409.0473.

[6] Luong, M.-T., Pham, H., & Manning, C. D. (2015). *Effective Approaches to Attention-based Neural Machine Translation.* Proceedings of EMNLP 2015. arXiv:1508.04025.

[7] Glahn, H. R., & Lowry, D. A. (1972). *The Use of Model Output Statistics (MOS) in Objective Weather Forecasting.* Journal of Applied Meteorology, 11(8), 1203–1211.

[8] Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree.* Advances in Neural Information Processing Systems (NeurIPS) 30.

[9] Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System.* Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.

[10] Hersbach, H., Bell, B., Berrisford, P., et al. (2020). *The ERA5 Global Reanalysis.* Quarterly Journal of the Royal Meteorological Society, 146(730), 1999–2049.

[11] Pedregosa, F., Varoquaux, G., Gramfort, A., et al. (2011). *Scikit-learn: Machine Learning in Python* (source of `MinMaxScaler`, used throughout this project's feature scaling, §3.4). Journal of Machine Learning Research, 12, 2825–2830.

[12] Chollet, F., et al. *Keras* (the deep learning framework used to build, train, and serve every recurrent model in this project). https://keras.io

[13] Open-Meteo. *Open-Meteo Weather API* (forecast + historical archive endpoints used throughout `extra/`'s tooling, §2, §8.2, §9). https://open-meteo.com

[14] WeatherAPI.com. *WeatherAPI.com Documentation* (the production backend's live upstream weather provider, §2, §6.2). https://www.weatherapi.com

---

*Document generated from direct inspection of this repository's source code and trained model artifacts. File paths and line numbers are accurate as of the commit this document was written against; if the code changes, re-verify rather than assuming this document has kept pace.*
