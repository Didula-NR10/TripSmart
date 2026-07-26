"""
backtest.py
────────────
The rigorous version of compute_bias_correction.py: instead of comparing the
model's prediction against Open-Meteo's own forecast (a proxy — it hasn't
happened yet either), this checks the model against Open-Meteo's HISTORICAL
ARCHIVE — actual recorded/reanalysis weather, i.e. real ground truth.

For one district, it fetches N days of real hourly history, then slides a
window through it: at every origin timestamp, feed the model the preceding
168 real hours (exactly like production does) and compare its 24h prediction
against what the archive says actually happened next.

It reports honest, out-of-sample numbers: the bias-correction table is fitted
on the first ~70% of origins (chronologically) and evaluated on the held-out
last ~30% it never saw — the same discipline you'd want from any model
evaluation. It also validates the currently-shipped correction table (in
model_pipeline.py / Backend/forecast/utils.py) against this same holdout, so
you can see whether it's actually helping.

Usage:
    python backtest.py                       # Colombo, 40 days, 6h step
    python backtest.py Kandy 60 4             # district, days_back, step_hours
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    HUMIDITY_BIAS_CORRECTION_PCT as SHIPPED_HUMIDITY_BIAS,
    INPUT_WINDOW,
    RAIN_ZERO_FLOOR_MM,
    TARGET_HORIZON,
    TEMP_BIAS_CORRECTION_C as SHIPPED_TEMP_BIAS,
    fetch_archive,
    run_model,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ARCHIVE_LAG_DAYS = 3   # avoid the last couple of days, which may still be preliminary ERA5T
TRAIN_FRACTION = 0.7   # chronological split — fit correction on the past, test on the future


def run_backtest(district: str, days_back: int, step_hours: int):
    end = datetime.now() - timedelta(days=ARCHIVE_LAG_DAYS)
    start = end - timedelta(days=days_back + 8)  # +8 buffer for the first context window

    print(f"Fetching {days_back + 8} days of archive history for {district} "
          f"({start:%Y-%m-%d} to {end:%Y-%m-%d})...")
    df = fetch_archive(district, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    df = df.reset_index(drop=True)
    n = len(df)

    origins = list(range(INPUT_WINDOW - 1, n - TARGET_HORIZON, step_hours))
    print(f"{n} hourly rows fetched -> {len(origins)} backtest origins "
          f"(every {step_hours}h, {INPUT_WINDOW}h context + {TARGET_HORIZON}h horizon each).")

    raw_temp = np.full((len(origins), TARGET_HORIZON), np.nan)
    raw_rain = np.full((len(origins), TARGET_HORIZON), np.nan)
    raw_hum = np.full((len(origins), TARGET_HORIZON), np.nan)
    actual_temp = np.full((len(origins), TARGET_HORIZON), np.nan)
    actual_rain = np.full((len(origins), TARGET_HORIZON), np.nan)
    actual_hum = np.full((len(origins), TARGET_HORIZON), np.nan)
    origin_times = []

    for row, o in enumerate(origins):
        context = df.iloc[o - INPUT_WINDOW + 1: o + 1].reset_index(drop=True)
        future = df.iloc[o + 1: o + 1 + TARGET_HORIZON].reset_index(drop=True)

        try:
            real = run_model(context)  # (24, 3) raw temp/rain/humidity, no clamp/floor/bias
        except Exception as e:
            print(f"  origin {df['datetime'].iloc[o]}: skipped ({e})")
            continue

        raw_temp[row] = real[:, 0]
        raw_rain[row] = real[:, 1]
        raw_hum[row] = real[:, 2]
        actual_temp[row] = future["Temperature_C"].values
        actual_rain[row] = future["Precipitation_mm"].values
        actual_hum[row] = future["Humidity_%"].values
        origin_times.append(df["datetime"].iloc[o])

        if (row + 1) % 25 == 0:
            print(f"  {row + 1}/{len(origins)} origins done...")

    valid = ~np.isnan(raw_temp[:, 0])
    raw_temp, raw_rain, raw_hum = raw_temp[valid], raw_rain[valid], raw_hum[valid]
    actual_temp, actual_rain, actual_hum = actual_temp[valid], actual_rain[valid], actual_hum[valid]
    print(f"{valid.sum()} origins usable.")

    return {
        "raw_temp": raw_temp, "raw_rain": raw_rain, "raw_hum": raw_hum,
        "actual_temp": actual_temp, "actual_rain": actual_rain, "actual_hum": actual_hum,
        "origin_times": origin_times,
    }


def mae(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - actual)))


def apply_floor(rain: np.ndarray, floor: float = RAIN_ZERO_FLOOR_MM) -> np.ndarray:
    return np.where(rain <= floor, 0.0, rain)


def evaluate(district: str, data: dict) -> None:
    n = len(data["raw_temp"])
    split = int(n * TRAIN_FRACTION)
    if split < 5 or n - split < 5:
        raise SystemExit(f"Not enough origins ({n}) for a train/holdout split — widen the date range.")

    train = slice(0, split)
    hold = slice(split, n)

    # ---- bias correction: fit on train, evaluate on holdout only ----
    temp_bias = np.mean(data["actual_temp"][train] - data["raw_temp"][train], axis=0)
    hum_bias = np.mean(data["actual_hum"][train] - data["raw_hum"][train], axis=0)

    raw_temp_hold, actual_temp_hold = data["raw_temp"][hold], data["actual_temp"][hold]
    raw_hum_hold, actual_hum_hold = data["raw_hum"][hold], data["actual_hum"][hold]
    raw_rain_hold, actual_rain_hold = data["raw_rain"][hold], data["actual_rain"][hold]

    corrected_temp_hold = raw_temp_hold + temp_bias
    corrected_hum_hold = raw_hum_hold + hum_bias
    shipped_temp_hold = raw_temp_hold + np.array(SHIPPED_TEMP_BIAS)
    shipped_hum_hold = raw_hum_hold + np.array(SHIPPED_HUMIDITY_BIAS)

    print(f"\n{'=' * 72}")
    print(f"BACKTEST RESULTS — {district}  ({n} origins total, {split} train / {n - split} holdout)")
    print(f"{'=' * 72}")

    print(f"\nTemperature MAE on HELD-OUT origins (deg C):")
    print(f"  raw model (no correction):        {mae(raw_temp_hold, actual_temp_hold):.3f}")
    print(f"  currently shipped correction:     {mae(shipped_temp_hold, actual_temp_hold):.3f}")
    print(f"  backtest-derived correction:      {mae(corrected_temp_hold, actual_temp_hold):.3f}")

    print(f"\nHumidity MAE on HELD-OUT origins (%):")
    print(f"  raw model (no correction):        {mae(raw_hum_hold, actual_hum_hold):.3f}")
    print(f"  currently shipped correction:     {mae(shipped_hum_hold, actual_hum_hold):.3f}")
    print(f"  backtest-derived correction:      {mae(corrected_hum_hold, actual_hum_hold):.3f}")

    floored_hold = apply_floor(raw_rain_hold)
    dry_hours = actual_rain_hold <= 0.0
    print(f"\nPrecipitation on HELD-OUT origins (mm), {int(dry_hours.sum())} of "
          f"{dry_hours.size} hours were genuinely dry:")
    print(f"  raw model MAE (no floor):         {mae(raw_rain_hold, actual_rain_hold):.3f}")
    print(f"  with {RAIN_ZERO_FLOOR_MM}mm zero-floor MAE:    {mae(floored_hold, actual_rain_hold):.3f}")
    print(f"  raw model, mean predicted rain on dry hours:      {raw_rain_hold[dry_hours].mean():.3f} mm"
          if dry_hours.any() else "")
    print(f"  floored model, mean predicted rain on dry hours:  {floored_hold[dry_hours].mean():.3f} mm"
          if dry_hours.any() else "")

    print(f"\nNew backtest-derived correction (paste into model_pipeline.py AND "
          f"Backend/forecast/utils.py):\n")
    print("TEMP_BIAS_CORRECTION_C = [")
    print("    " + ", ".join(f"{v:.3f}" for v in temp_bias))
    print("]")
    print("\nHUMIDITY_BIAS_CORRECTION_PCT = [")
    print("    " + ", ".join(f"{v:.3f}" for v in hum_bias))
    print("]")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = pd.DataFrame({
        "origin_time": data["origin_times"],
        **{f"raw_temp_h{i+1}": data["raw_temp"][:, i] for i in range(TARGET_HORIZON)},
        **{f"actual_temp_h{i+1}": data["actual_temp"][:, i] for i in range(TARGET_HORIZON)},
        **{f"raw_hum_h{i+1}": data["raw_hum"][:, i] for i in range(TARGET_HORIZON)},
        **{f"actual_hum_h{i+1}": data["actual_hum"][:, i] for i in range(TARGET_HORIZON)},
        **{f"raw_rain_h{i+1}": data["raw_rain"][:, i] for i in range(TARGET_HORIZON)},
        **{f"actual_rain_h{i+1}": data["actual_rain"][:, i] for i in range(TARGET_HORIZON)},
    })
    out_path = OUTPUT_DIR / f"backtest_{district.lower()}.csv"
    out.to_csv(out_path, index=False)
    print(f"\nPer-origin results saved to {out_path}")


def main() -> None:
    district = sys.argv[1] if len(sys.argv) > 1 else "Colombo"
    days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    step_hours = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    if district not in DISTRICT_COORDS:
        print(f"Unknown district '{district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    data = run_backtest(district, days_back, step_hours)
    evaluate(district, data)


if __name__ == "__main__":
    main()
