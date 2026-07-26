"""
alternate_models/run_forecast.py
───────────────────────────────────
Run any trained model from this folder (01_gru_seq2seq, 02_bidirectional_lstm,
03_seq2seq_attention, or 04_lightgbm_multioutput) against LIVE Open-Meteo
data and print its next-24h forecast — the alternate-models equivalent of
../run_forecast.py, but for whichever candidate model you point it at.

Usage:
    python run_forecast.py 01_gru_seq2seq
    python run_forecast.py 04_lightgbm_multioutput --district Kandy

Requires that model's train.py has already been run (looks for its
artifacts/ folder).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
COMMON_DIR = THIS_DIR / "common"
sys.path.insert(0, str(COMMON_DIR))

from inference import load_trained_model, predict_next_24h  # noqa: E402
from live_fetch import fetch_live_context  # noqa: E402
from model_pipeline import DISTRICT_COORDS  # noqa: E402 (via live_fetch's sys.path insert)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a trained alternate model against live Open-Meteo data")
    p.add_argument("model_dir", type=str, help="e.g. 01_gru_seq2seq")
    p.add_argument("--district", type=str, default="Colombo")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.district not in DISTRICT_COORDS:
        print(f"Unknown district '{args.district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    model_dir = THIS_DIR / args.model_dir
    print(f"Loading model from {model_dir} ...")
    loaded = load_trained_model(model_dir)
    print(f"Model kind: {loaded['kind']}")

    past_days = 20 if loaded["kind"] == "gbm" else 8
    print(f"Fetching {past_days} days of live context for {args.district} from Open-Meteo...")
    context_df = fetch_live_context(args.district, past_days=past_days)

    real = predict_next_24h(loaded, context_df)
    last_obs = context_df["datetime"].iloc[-1]

    print(f"\nLast observation (Colombo time): {last_obs}")
    print(f"\n{'Hour':<6}{'Valid time':<20}{'Temp (C)':<12}{'Rain (mm)':<12}{'Humidity (%)':<14}")
    print("-" * 64)
    for i in range(24):
        valid = last_obs + pd.Timedelta(hours=i + 1)
        temp, rain, hum = real[i]
        print(f"{i + 1:<6}{valid.strftime('%Y-%m-%d %H:%M'):<20}{temp:<12.1f}{max(0.0, rain):<12.3f}{hum:<14.1f}")
    print()


if __name__ == "__main__":
    main()
