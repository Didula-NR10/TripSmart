"""
training.pipeline
────────────────────
The orchestrator: collect -> retrain -> test -> deploy-only-if-better, as
one script. Run manually (`python -m training.pipeline` from Backend/, with
SUPABASE_DB_URL set) or on a schedule via
.github/workflows/retrain-model.yml.

This script NEVER pushes to git and never touches Render — it only decides
whether a candidate model earns a place in the working tree
(Backend/models/best_checkpoint.keras + bias_correction.json) and reports
its reasoning. Turning a promoted candidate into a live deployment is the
calling workflow's job (open a PR; merging it is what redeploys).

Exit behavior:
  - Not enough real data yet          -> report says so, nothing touched, exit 0.
  - Candidate does not beat current   -> report says so, nothing touched, exit 0.
  - Candidate beats current           -> Backend/models/ is updated in place,
                                          report says PROMOTED, exit 0.
Every path exits 0 on success; a real failure (e.g. can't reach the
database) raises and exits non-zero so CI shows a red run instead of a
silently-empty report.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Backend/ on sys.path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.pipeline")


def _write_github_output(promoted: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"promoted={'true' if promoted else 'false'}\n")


def _render_markdown(report: dict) -> str:
    c, cur = report["candidate_metrics"], report["current_metrics"]
    lines = [
        f"# Retrain report — {report['timestamp']}",
        "",
        f"**Outcome: {'PROMOTED' if report['promoted'] else 'kept current model'}** — {report['reason']}",
        "",
        f"- Districts with data: {report['n_districts']}",
        f"- Total windows: {report['n_windows']} "
        f"(train {report['n_train']} / val {report['n_val']} / holdout {report['n_holdout']})",
        "",
        "| Metric | Current (deployed) | Candidate |",
        "|---|---|---|",
        f"| Temperature MAE (°C) | {cur['temp_mae']:.3f} | {c['temp_mae']:.3f} |",
        f"| Humidity MAE (%) | {cur['humidity_mae']:.3f} | {c['humidity_mae']:.3f} |",
        f"| Rain MAE, floored (mm, informational — not gated) | {cur['rain_mae_floored']:.3f} | {c['rain_mae_floored']:.3f} |",
        "",
    ]
    if report.get("bias_table_report"):
        lines.append("## Per-district bias correction (candidate)")
        lines.append("")
        lines.append("| District | Origins | Temp correction | Humidity correction |")
        lines.append("|---|---|---|---|")
        for district, r in sorted(report["bias_table_report"].items()):
            if r.get("status"):
                lines.append(f"| {district} | {r['n_origins']} | {r['status']} | {r['status']} |")
            else:
                lines.append(
                    f"| {district} | {r['n_origins']} | "
                    f"{'kept' if r['use_temp_correction'] else 'dropped'} "
                    f"({r['temp_mae_raw']:.3f} -> {r['temp_mae_corrected']:.3f}) | "
                    f"{'kept' if r['use_hum_correction'] else 'dropped'} "
                    f"({r['hum_mae_raw']:.3f} -> {r['hum_mae_corrected']:.3f}) |"
                )
    return "\n".join(lines)


def main() -> int:
    from core.config import settings
    from training import config as tcfg
    from training.bias_tables import regenerate as regenerate_bias_tables
    from training.dataset import build_windows, chronological_split, scale_features, scale_targets
    from training.evaluate import evaluate_model, is_better
    from training.finetune import fine_tune
    from training.pull_data import fetch_all_districts

    tcfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    report: dict = {"timestamp": timestamp, "promoted": False}

    log.info("Step 1/6: pulling accumulated real observations from Supabase...")
    district_frames = fetch_all_districts()
    if not district_frames:
        report["reason"] = "weather_observations is empty — no data has accumulated yet."
        _finish(report, promoted=False)
        return 0

    log.info("Step 2/6: building windows...")
    X, y, dt_list, dist_list = build_windows(district_frames)
    report["n_districts"] = len(set(dist_list))
    report["n_windows"] = len(X)

    if len(X) < tcfg.MIN_TOTAL_WINDOWS:
        report["reason"] = (
            f"only {len(X)} windows available across {report['n_districts']} district(s), "
            f"need at least {tcfg.MIN_TOTAL_WINDOWS} — skipping this cycle."
        )
        log.info(report["reason"])
        _finish(report, promoted=False)
        return 0

    split = chronological_split(X, y, dt_list, dist_list)
    report["n_train"] = len(split["train"]["X"])
    report["n_val"] = len(split["val"]["X"])
    report["n_holdout"] = len(split["holdout"]["X"])
    if report["n_val"] == 0 or report["n_holdout"] == 0:
        report["reason"] = "train/val/holdout split left an empty split — need more accumulated data."
        _finish(report, promoted=False)
        return 0

    log.info("Step 3/6: loading the currently deployed model...")
    import tensorflow as tf
    import joblib

    current_model = tf.keras.models.load_model(settings.MODEL_PATH)
    scaler = joblib.load(settings.SCALER_PATH)

    X_train_s = scale_features(split["train"]["X"], scaler)
    y_train_s = scale_targets(split["train"]["y"], scaler)
    X_val_s = scale_features(split["val"]["X"], scaler)
    y_val_s = scale_targets(split["val"]["y"], scaler)

    holdout_scaled = {**split["holdout"], "X": scale_features(split["holdout"]["X"], scaler)}

    log.info("Step 4/6: evaluating the CURRENT model on the held-out slice...")
    current_metrics = evaluate_model(current_model, scaler, holdout_scaled["X"], split["holdout"]["y"])
    report["current_metrics"] = current_metrics

    log.info("Step 5/6: fine-tuning a candidate...")
    candidate_model, history = fine_tune(current_model, X_train_s, y_train_s, X_val_s, y_val_s)
    candidate_metrics = evaluate_model(candidate_model, scaler, holdout_scaled["X"], split["holdout"]["y"])
    report["candidate_metrics"] = candidate_metrics
    report["training_history_last_epoch"] = {k: v[-1] for k, v in history.items()}

    log.info("Step 6/6: deciding whether the candidate is good enough to promote...")
    promoted, reason = is_better(candidate_metrics, current_metrics)
    report["reason"] = reason
    log.info("Decision: %s (%s)", "PROMOTE" if promoted else "KEEP CURRENT", reason)

    if promoted:
        temp_table, hum_table, bias_report = regenerate_bias_tables(candidate_model, scaler, holdout_scaled)
        report["bias_table_report"] = bias_report

        tcfg.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        candidate_model.save(settings.MODEL_PATH)
        tcfg.BIAS_TABLE_JSON_PATH.write_text(json.dumps(
            {"temp_bias_correction_c": temp_table, "humidity_bias_correction_pct": hum_table},
            indent=2,
        ))
        log.info("Wrote %s and %s.", settings.MODEL_PATH, tcfg.BIAS_TABLE_JSON_PATH)

    _finish(report, promoted=promoted)
    return 0


def _finish(report: dict, promoted: bool) -> None:
    from training import config as tcfg

    report["promoted"] = promoted
    tcfg.REPORT_JSON_PATH.write_text(json.dumps(report, indent=2, default=str))
    tcfg.REPORT_MD_PATH.write_text(_render_markdown(report) if "candidate_metrics" in report else (
        f"# Retrain report — {report['timestamp']}\n\n"
        f"**Outcome: skipped** — {report['reason']}\n"
    ))
    _write_github_output(promoted)
    log.info("Report written to %s / %s", tcfg.REPORT_JSON_PATH, tcfg.REPORT_MD_PATH)


if __name__ == "__main__":
    raise SystemExit(main())
