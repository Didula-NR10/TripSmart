from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.print_accuracy_table")

def _fmt(v, digits=3):
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) else str(v)

def build_rows(baseline: dict) -> list[list[str]]:
    m = baseline["metrics"]
    return [
        ["Temperature", "MAE (°C)", _fmt(m["temp_mae"])],
        ["Temperature", "RMSE (°C)", _fmt(m["temp_rmse"])],
        ["Temperature", "R²", _fmt(m["temp_r2"])],
        ["Humidity", "MAE (%)", _fmt(m["humidity_mae"])],
        ["Humidity", "RMSE (%)", _fmt(m["humidity_rmse"])],
        ["Humidity", "R²", _fmt(m["humidity_r2"])],
        ["Rain (raw)", "MAE (mm)", _fmt(m["rain_mae_raw"])],
        ["Rain (zero-floored)", "MAE (mm)", _fmt(m["rain_mae_floored"])],
        ["Rain (zero-floored)", "RMSE (mm)", _fmt(m["rain_rmse_floored"])],
        ["Rain (zero-floored)", "R²", _fmt(m["rain_r2_floored"])],
    ]

def render_text(baseline: dict, rain_hurdle: dict | None) -> str:
    rows = build_rows(baseline)
    col_widths = [22, 14, 10]
    header = ["Channel", "Metric", "Value"]

    def fmt_row(cells):
        return "  ".join(str(c).ljust(w) for c, w in zip(cells, col_widths))

    lines = [
        "TripSmart Forecast Model — Deployed Model Accuracy",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Measured against {baseline['n_holdout']:,} genuinely held-out real hourly windows "
        if "n_holdout" in baseline else "",
        f"({baseline.get('n_districts', '?')} districts, holdout period "
        f"{baseline.get('holdout_period', 'unknown')})",
        "=" * 60,
        fmt_row(header),
        "-" * 60,
    ]
    for row in rows:
        lines.append(fmt_row(row))
    lines.append("=" * 60)
    lines.append("R² close to 1 = explains real variance well. R² close to 0 = no")
    lines.append("better than always predicting the average. This is expected to")
    lines.append("be strong for temperature/humidity and weak for rain — rain at")
    lines.append("hourly resolution is inherently close to unpredictable from")
    lines.append("historical weather alone (see project documentation).")

    if rain_hurdle:
        lines.append("")
        lines.append("Rain hurdle-model experiment (IN PROGRESS, not yet production-ready):")
        lines.append(f"  Baseline (raw GRU) rain MAE:      {rain_hurdle['baseline_floored_gru_rain_mae']}")
        lines.append(f"  Hurdle-model rain MAE:            {rain_hurdle['hurdle_combined_rain_mae']}")
        oc = rain_hurdle["occurrence_classification"]
        lines.append(f"  Rain-occurrence precision/recall: {oc['precision']} / {oc['recall']}")
        lines.append("  Class-weighting fixed recall (was 0.007 pre-fix) but precision/overall")
        lines.append("  MAE haven't beaten baseline yet — this points at the frozen encoder's")
        lines.append("  summary vector lacking rain-specific signal, not at more weight-tuning.")
        lines.append("  Next lever: extended features (pressure, dew point, wind direction,")
        lines.append("  rain lags) on a fresh, non-frozen model.")

    return "\n".join(lines)

def render_image(baseline: dict, rain_hurdle: dict | None, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = build_rows(baseline)
    col_labels = ["Channel", "Metric", "Value"]

    n_extra_rows = 4 if rain_hurdle else 0
    fig_height = 1.1 + 0.34 * (len(rows) + n_extra_rows)
    fig, ax = plt.subplots(figsize=(8.5, fig_height))
    ax.axis("off")

    title = "TripSmart Forecast Model — Deployed Model Accuracy"
    subtitle = (
        f"Measured on {baseline['n_holdout']:,} held-out real hourly windows · "
        f"{baseline.get('n_districts', '?')} districts · "
        f"holdout period {baseline.get('holdout_period', 'unknown')}"
    )
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.985)
    ax.set_title(subtitle, fontsize=8.5, color="#555555", pad=14, loc="center")

    table_rows = rows.copy()
    row_colors = ["#EAF4F4"] * len(rows)
    for i, r in enumerate(table_rows):
        if r[0].startswith("Rain") and r[1] == "R²":
            row_colors[i] = "#FBE4DD"

    if rain_hurdle:
        oc = rain_hurdle["occurrence_classification"]
        table_rows += [
            ["— Rain hurdle experiment (in progress) —", "", ""],
            ["Rain hurdle", "MAE (mm)", _fmt(rain_hurdle["hurdle_combined_rain_mae"])],
            ["Rain hurdle", "Occurrence recall", f"{oc['recall']}"],
            ["Rain hurdle", "Occurrence precision", f"{oc['precision']}"],
        ]
        row_colors += ["#F0F0F0", "#FBEDD3", "#FBEDD3", "#FBEDD3"]

    table = ax.table(
        cellText=table_rows,
        colLabels=col_labels,
        cellLoc="left",
        colLoc="left",
        loc="upper center",
        cellColours=[[c] * 3 for c in row_colors],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1, 1.6)
    table.auto_set_column_width([0, 1, 2])

    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight="bold", color="white")
            cell.set_facecolor("#1D6E82")
        cell.set_edgecolor("#CBD5D3")

    fig.text(
        0.02, 0.01,
        "R² near 1 = strong fit. Near 0 = weak (rain at hourly resolution is inherently\n"
        "close to unpredictable from historical weather alone — see project documentation).",
        fontsize=7.3, color="#666666",
    )

    plt.tight_layout(rect=[0, 0.08, 1, 0.94])
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

def main() -> int:
    from training import config as tcfg

    baseline_path = tcfg.OUTPUT_DIR / "baseline_report.json"
    if not baseline_path.exists():
        log.error("%s not found — run `python -m training.baseline_report` first.", baseline_path)
        return 1
    baseline = json.loads(baseline_path.read_text())

    hurdle_path = tcfg.OUTPUT_DIR / "rain_hurdle_report.json"
    rain_hurdle = json.loads(hurdle_path.read_text()) if hurdle_path.exists() else None

    text = render_text(baseline, rain_hurdle)
    print(text)

    text_path = tcfg.OUTPUT_DIR / "accuracy_table.txt"
    text_path.write_text(text, encoding="utf-8")
    log.info("Text table saved to %s", text_path)

    image_path = tcfg.OUTPUT_DIR / "accuracy_table.png"
    render_image(baseline, rain_hurdle, image_path)
    log.info("Table image saved to %s", image_path)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
