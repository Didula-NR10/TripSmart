"""
compute_bias_correction.py
────────────────────────────
One-off analysis: run the GRU model against every district, compare each
lead hour (1..24) to Open-Meteo's own forecast for that same hour, and
average the residual (reference - predicted) per lead hour across all
districts. That gives a per-lead-hour bias-correction table.

This is a fast, no-retraining way to cancel out a systematic bias (e.g. the
model running consistently cold overnight, or humidity decaying too slowly)
without touching the trained weights.

NOTE: Open-Meteo's own forecast is a proxy for "truth" here, not the ground
truth itself — it's what's available immediately. extra/backtest.py (which
checks predictions against Open-Meteo's *historical archive*, i.e. what
actually happened) is the more rigorous version of this and can be used
later to recompute a better table.

Usage:
    python compute_bias_correction.py
Prints a Python-literal table ready to paste into model_pipeline.py /
Backend/forecast/utils.py, and saves the raw residuals to output/bias_residuals.csv.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    TARGET_HORIZON,
    clamp_physical,
    fetch_open_meteo,
    run_model,
    split_context_and_future,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def residuals_for_district(district: str):
    """(24,) arrays of (open_meteo - predicted) for temp and humidity, unclamped-bias version."""
    df = fetch_open_meteo(district, forecast_days=2)
    context, future = split_context_and_future(df)

    real = run_model(context)  # (24, 3) raw temp/rain/humidity, no bias correction yet
    om = future.head(TARGET_HORIZON).reset_index(drop=True)
    if len(om) < TARGET_HORIZON:
        return None

    temp_resid = np.full(TARGET_HORIZON, np.nan)
    hum_resid = np.full(TARGET_HORIZON, np.nan)
    for i in range(TARGET_HORIZON):
        temp, _, humidity = clamp_physical(real[i][0], real[i][1], real[i][2])
        temp_resid[i] = float(om["Temperature_C"].iloc[i]) - temp
        hum_resid[i] = float(om["Humidity_%"].iloc[i]) - humidity
    return temp_resid, hum_resid


def main() -> None:
    districts = sorted(DISTRICT_COORDS)
    temp_rows = []
    hum_rows = []
    ok, failed = 0, 0

    for i, district in enumerate(districts):
        print(f"[{i + 1}/{len(districts)}] {district} ...", end=" ")
        try:
            result = residuals_for_district(district)
            if result is None:
                print("skipped (not enough future hours)")
                failed += 1
                continue
            temp_resid, hum_resid = result
            temp_rows.append(temp_resid)
            hum_rows.append(hum_resid)
            print("ok")
            ok += 1
        except Exception as e:
            print(f"failed ({e})")
            failed += 1
        time.sleep(1)  # be polite to Open-Meteo's free/keyless tier

    if not temp_rows:
        raise SystemExit("No districts succeeded — cannot compute a bias table.")

    temp_matrix = np.array(temp_rows)   # (n_districts, 24)
    hum_matrix = np.array(hum_rows)

    temp_bias = np.nanmean(temp_matrix, axis=0)
    hum_bias = np.nanmean(hum_matrix, axis=0)

    OUTPUT_DIR.mkdir(exist_ok=True)
    pd.DataFrame(temp_matrix, index=districts[:len(temp_rows)],
                 columns=[f"h{i+1}" for i in range(TARGET_HORIZON)]).to_csv(
        OUTPUT_DIR / "bias_residuals_temp.csv"
    )
    pd.DataFrame(hum_matrix, index=districts[:len(hum_rows)],
                 columns=[f"h{i+1}" for i in range(TARGET_HORIZON)]).to_csv(
        OUTPUT_DIR / "bias_residuals_humidity.csv"
    )

    print(f"\n{ok} districts used, {failed} skipped/failed.")
    print("\nTEMP_BIAS_CORRECTION_C = [")
    print("    " + ", ".join(f"{v:.3f}" for v in temp_bias))
    print("]")
    print("\nHUMIDITY_BIAS_CORRECTION_PCT = [")
    print("    " + ", ".join(f"{v:.3f}" for v in hum_bias))
    print("]")
    print(f"\nRaw residuals saved to {OUTPUT_DIR}/bias_residuals_temp.csv and bias_residuals_humidity.csv")


if __name__ == "__main__":
    main()
