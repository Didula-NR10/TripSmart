"""
training.config
────────────────
Knobs for the retraining pipeline, isolated from the serving app's
core.config so tuning a retrain threshold never risks touching what the
live API reads. Everything here can be overridden with an env var of the
same name, so CI can adjust behavior without a code change.
"""
from __future__ import annotations

import os
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TRAINING_DIR.parent
MODELS_DIR = BACKEND_DIR / "models"
OUTPUT_DIR = TRAINING_DIR / "output"

# A window needs this many hours of contiguous real observations (168 context
# + 24 horizon). Below this, a district contributes nothing this cycle.
INPUT_WINDOW = 168
TARGET_HORIZON = 24
MIN_HOURS_PER_DISTRICT = INPUT_WINDOW + TARGET_HORIZON

# If fewer than this many windows exist across ALL districts combined, the
# pipeline refuses to train at all rather than fine-tune on noise. Early on
# (first weeks after launch) this will trip almost every run — that is the
# correct, boring outcome, not a bug. Tune upward once you've seen real
# accumulation rates in weather_observations.
MIN_TOTAL_WINDOWS = int(os.environ.get("RETRAIN_MIN_TOTAL_WINDOWS", "300"))

# Chronological split — earliest windows train, next validate, most recent
# (per district) are the untouched holdout the promotion decision is made on.
TRAIN_FRACTION = float(os.environ.get("RETRAIN_TRAIN_FRACTION", "0.70"))
VAL_FRACTION = float(os.environ.get("RETRAIN_VAL_FRACTION", "0.15"))
# remaining ~0.15 is holdout

# Fine-tuning hyperparameters. Deliberately conservative (small LR, few
# epochs, early stopping) because this warm-starts from the currently
# deployed checkpoint on a comparatively small new slice of real data —
# the goal is a nudge in the right direction, not retraining from scratch.
FINE_TUNE_LR = float(os.environ.get("RETRAIN_LR", "1e-4"))
FINE_TUNE_MAX_EPOCHS = int(os.environ.get("RETRAIN_MAX_EPOCHS", "60"))
FINE_TUNE_BATCH_SIZE = int(os.environ.get("RETRAIN_BATCH_SIZE", "32"))
EARLY_STOPPING_PATIENCE = int(os.environ.get("RETRAIN_EARLY_STOPPING_PATIENCE", "8"))

# A candidate only gets promoted if its (temp_mae + humidity_mae) average
# beats the currently-deployed model's by at least this fraction. Guards
# against redeploying on noise for a marginal, statistically meaningless
# "improvement". Rain is excluded from the gate because production doesn't
# serve the GRU's own rain channel at all (see SYSTEM_DOCUMENTATION.md §5.3).
PROMOTION_MARGIN = float(os.environ.get("RETRAIN_PROMOTION_MARGIN", "0.005"))  # 0.5%

# Bias-correction re-fit (mirrors extra/backtest.py's fit_and_evaluate):
# fraction of each district's holdout windows used to FIT the correction,
# evaluated on the rest of that same holdout.
BIAS_FIT_FRACTION = float(os.environ.get("RETRAIN_BIAS_FIT_FRACTION", "0.70"))
MIN_ORIGINS_FOR_BIAS_FIT = 20  # below this, leave that district uncorrected (zero list)

# Moderates the rain-occurrence class weight (see rain_hurdle.occurrence_pos_weight).
# 1.0 = full inverse-frequency ratio; empirically too aggressive in a live run
# (recall 0.7% -> 64% but precision collapsed 59% -> 19%, net MAE/R2 worse).
RAIN_POS_WEIGHT_DAMPING = float(os.environ.get("RAIN_POS_WEIGHT_DAMPING", "0.35"))

RAIN_ZERO_FLOOR_MM = 0.3  # must match Backend/forecast/utils.py exactly

REPORT_JSON_PATH = OUTPUT_DIR / "retrain_report.json"
REPORT_MD_PATH = OUTPUT_DIR / "retrain_report.md"
BIAS_TABLE_JSON_PATH = MODELS_DIR / "bias_correction.json"
