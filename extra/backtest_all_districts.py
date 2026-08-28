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

        pd.DataFrame(summary_rows).to_csv(OUTPUT_DIR / "backtest_all_summary.csv", index=False)
        with open(OUTPUT_DIR / "backtest_all_results.json", "w") as f:
            json.dump(
                {d: {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in r.items()}
                 for d, r in results.items()},
                f, indent=2,
            )

        time.sleep(1)

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
