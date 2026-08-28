from __future__ import annotations

DATA_PATH = "sri_lanka_labeled_extended.parquet"

DISTRICT_SHEETS = [
    "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "NuwaraEliya",
    "Galle", "Matara", "Hambantota", "Jaffna", "Kilinochchi", "Mannar",
    "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
    "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
    "Monaragala", "Ratnapura", "Kegalle",
]

CLIMATE_ZONES = [1, 2, 3, 4]
WINDOW_STRIDE = 10
TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
RAIN_ZERO_FLOOR_MM = 0.3
GRU1_UNITS = 128
GRU2_UNITS = 64
RAIN_HIDDEN_UNITS = 48
DROPOUT_RATE = 0.35
L2_REG = 1e-4
LEARNING_RATE = 5e-4
MAX_EPOCHS = 60
BATCH_SIZE = 32
EARLY_STOPPING_PATIENCE = 6
RAIN_POS_WEIGHT_DAMPING = 0.35
OUTPUT_DIR = "output"
