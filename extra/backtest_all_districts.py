"""
backtest_all_districts.py
────────────────────────────
Runs backtest.py's holdout method separately for every one of the 25
districts (instead of just Colombo), because climate varies a lot across Sri
Lanka — coastal, hill-country, dry-zone — so a bias fitted on Colombo doesn't
necessarily transfer anywhere else.

For each district: fetch its own historical archive, fit a temperature and
humidity correction on the first ~70% of origins (chronologically), and only
keep that district's correction if it actually beats the raw model on the
untouched last ~30% (same discipline as backtest.py — a correction that
doesn't prove itself out-of-sample is discarded, not shipped).

Saves incrementally after every district (output/backtest_all_summary.csv +
output/backtest_all_results.json) so a mid-run failure doesn't lose earlier
work. At the end, prints the final per-district TEMP_BIAS_CORRECTION_C /
HUMIDITY_BIAS_CORRECTION_PCT dicts ready to paste into model_pipeline.py and
Backend/forecast/utils.py.

This takes a while — 25 districts x ~165 origins each. Expect it to run for
a good chunk of an hour on CPU.

Usage:
    python backtest_all_districts.py                 # all 25, 40 days, 6h step
    python backtest_all_districts.py 30 8             # days_back, step_hours
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

from backtest import fit_and_evaluate, run_backtest
from model_pipeline import DISTRICT_COORDS

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> None:
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    step_hours = int(sys.argv[2]) if len(sys.argv) > 2 else 6

    districts = sorted(DISTRICT_COORDS)
    results: dict[str, dict] = {}
    OUTPUT_DIR.mkdir(exist_ok=True)
    summary_rows = []

    for i, district in enumerate(districts):
        print(f"\n[{i + 1}/{len(districts)}] {district} " + "=" * 40)
        try:
            data = run_backtest(district, days_back, step_hours)
            r = fit_and_evaluate(district, data)
        except Exception as e:
            print(f"  FAILED: {e}")
            time.sleep(2)
            continue

        results[district] = r
        summary_rows.append({
            "district": district,
            "n_holdout": r["n_holdout"],
            "temp_mae_raw": round(r["temp_mae_raw"], 3),
            "temp_mae_backtest": round(r["temp_mae_backtest"], 3),
            "use_temp_correction": r["use_temp_correction"],
            "hum_mae_raw": round(r["hum_mae_raw"], 3),
            "hum_mae_backtest": round(r["hum_mae_backtest"], 3),
            "use_hum_correction": r["use_hum_correction"],
            "rain_mae_raw": round(r["rain_mae_raw"], 3),
            "rain_mae_floored": round(r["rain_mae_floored"], 3),
        })
        print(f"  temp MAE raw={r['temp_mae_raw']:.3f} backtest={r['temp_mae_backtest']:.3f} "
              f"({'use correction' if r['use_temp_correction'] else 'keep raw'})")
        print(f"  hum  MAE raw={r['hum_mae_raw']:.3f} backtest={r['hum_mae_backtest']:.3f} "
              f"({'use correction' if r['use_hum_correction'] else 'keep raw'})")

        # Save incrementally so a later failure doesn't lose earlier districts.
        pd.DataFrame(summary_rows).to_csv(OUTPUT_DIR / "backtest_all_summary.csv", index=False)
        with open(OUTPUT_DIR / "backtest_all_results.json", "w") as f:
            json.dump(
                {d: {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in r.items()}
                 for d, r in results.items()},
                f, indent=2,
            )

        time.sleep(1)  # be polite to Open-Meteo between districts

    # ---- final tables: only districts whose correction proved itself ----
    temp_table = {d: r["temp_bias"].tolist() for d, r in results.items() if r["use_temp_correction"]}
    hum_table = {d: r["hum_bias"].tolist() for d, r in results.items() if r["use_hum_correction"]}

    print(f"\n{'=' * 72}")
    print(f"DONE — {len(results)}/{len(districts)} districts backtested.")
    print(f"{sum(r['use_temp_correction'] for r in results.values())} districts get a temperature correction.")
    print(f"{sum(r['use_hum_correction'] for r in results.values())} districts get a humidity correction.")
    print(f"{'=' * 72}")

    def fmt_table(name: str, table: dict) -> str:
        lines = [f"{name}: dict[str, list[float]] = {{"]
        for d in sorted(table):
            lines.append(f'    "{d}": [' + ", ".join(f"{v:.3f}" for v in table[d]) + "],")
        lines.append("}")
        return "\n".join(lines)

    print("\n" + fmt_table("TEMP_BIAS_CORRECTION_C", temp_table))
    print("\n" + fmt_table("HUMIDITY_BIAS_CORRECTION_PCT", hum_table))

    print(f"\nSummary CSV: {OUTPUT_DIR / 'backtest_all_summary.csv'}")
    print(f"Full results JSON: {OUTPUT_DIR / 'backtest_all_results.json'}")


if __name__ == "__main__":
    main()
