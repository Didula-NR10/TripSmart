from __future__ import annotations

import os
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TRAINING_DIR.parent
MODELS_DIR = BACKEND_DIR / "models"
OUTPUT_DIR = TRAINING_DIR / "output"

INPUT_WINDOW = 168
TARGET_HORIZON = 24
MIN_HOURS_PER_DISTRICT = INPUT_WINDOW + TARGET_HORIZON

MIN_TOTAL_WINDOWS = int(os.environ.get("RETRAIN_MIN_TOTAL_WINDOWS", "300"))

TRAIN_FRACTION = float(os.environ.get("RETRAIN_TRAIN_FRACTION", "0.70"))
VAL_FRACTION = float(os.environ.get("RETRAIN_VAL_FRACTION", "0.15"))

FINE_TUNE_LR = float(os.environ.get("RETRAIN_LR", "1e-4"))
FINE_TUNE_MAX_EPOCHS = int(os.environ.get("RETRAIN_MAX_EPOCHS", "60"))
FINE_TUNE_BATCH_SIZE = int(os.environ.get("RETRAIN_BATCH_SIZE", "32"))
EARLY_STOPPING_PATIENCE = int(os.environ.get("RETRAIN_EARLY_STOPPING_PATIENCE", "8"))

PROMOTION_MARGIN = float(os.environ.get("RETRAIN_PROMOTION_MARGIN", "0.005"))

BIAS_FIT_FRACTION = float(os.environ.get("RETRAIN_BIAS_FIT_FRACTION", "0.70"))
MIN_ORIGINS_FOR_BIAS_FIT = 20

RAIN_POS_WEIGHT_DAMPING = float(os.environ.get("RAIN_POS_WEIGHT_DAMPING", "0.35"))

RAIN_ZERO_FLOOR_MM = 0.3

REPORT_JSON_PATH = OUTPUT_DIR / "retrain_report.json"
REPORT_MD_PATH = OUTPUT_DIR / "retrain_report.md"
BIAS_TABLE_JSON_PATH = MODELS_DIR / "bias_correction.json"
