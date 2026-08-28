import os
import gc
import json
import numpy as np
import tensorflow as tf
from pathlib import Path
from datetime import datetime
from tensorflow.keras import Input, Model
from tensorflow.keras.layers import GRU, Dense, Dropout, Reshape
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.losses import Huber
from tensorflow.keras.callbacks import (
    EarlyStopping,
    ModelCheckpoint,
    ReduceLROnPlateau,
    TensorBoard,
    CSVLogger,
)

gpus = tf.config.list_physical_devices("GPU")
for gpu in gpus:
    try:
        tf.config.experimental.set_memory_growth(gpu, True)
    except RuntimeError:
        pass
print(f"[GPU] Visible devices: {gpus if gpus else 'NONE — running on CPU, this WILL be slow'}")

tf.keras.mixed_precision.set_global_policy("mixed_float16")

tf.keras.backend.clear_session()
gc.collect()

SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

BASE_DIR        = Path(__file__).resolve().parent
ARTIFACTS_DIR   = BASE_DIR / "artifacts"
MODELS_DIR      = BASE_DIR / "models"
LOGS_DIR        = BASE_DIR / "logs"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RUN_TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")
MODEL_SAVE_PATH = MODELS_DIR / "trip_smart_gru_forecaster.keras"
BEST_CKPT_PATH  = MODELS_DIR / "best_checkpoint.keras"
HISTORY_PATH    = MODELS_DIR / "training_history.json"
TB_LOG_DIR      = LOGS_DIR   / f"tensorboard_{RUN_TIMESTAMP}"
CSV_LOG_PATH    = LOGS_DIR   / f"training_log_{RUN_TIMESTAMP}.csv"

X_TRAIN_PATH    = ARTIFACTS_DIR / "X_train.npy"
Y_TRAIN_PATH    = ARTIFACTS_DIR / "y_train.npy"
X_VAL_PATH      = ARTIFACTS_DIR / "X_val.npy"
Y_VAL_PATH      = ARTIFACTS_DIR / "y_val.npy"
X_TEST_PATH     = ARTIFACTS_DIR / "X_test.npy"
Y_TEST_PATH     = ARTIFACTS_DIR / "y_test.npy"

INPUT_WINDOW        = 168
TARGET_HORIZON      = 24
NUM_FEATURES        = 12
NUM_TARGETS         = 3

GRU_UNITS_1         = 128
GRU_UNITS_2         = 64
DROPOUT_RATE        = 0.2
RECURRENT_DROPOUT   = 0.0

LEARNING_RATE       = 0.001
HUBER_DELTA         = 1.0
BATCH_SIZE          = 128
MAX_EPOCHS          = 100
EARLY_STOP_PATIENCE = 5
LR_REDUCE_PATIENCE  = 3
LR_REDUCE_FACTOR    = 0.5
LR_MIN              = 1e-6

SHUFFLE_BUFFER      = 4096

def make_dataset(x_path: Path, y_path: Path, batch_size: int, shuffle: bool) -> tf.data.Dataset:
    X = np.load(x_path, mmap_mode="r")
    y = np.load(y_path, mmap_mode="r")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X/y row mismatch: {X.shape[0]} vs {y.shape[0]} for {x_path.name}")

    n = X.shape[0]

    def gen():
        if shuffle:
            order = np.random.permutation(n)
        else:
            order = np.arange(n)
        for i in range(0, n, batch_size):
            idx = order[i : i + batch_size]
            idx_sorted = np.sort(idx)
            Xb = np.asarray(X[idx_sorted], dtype=np.float32)
            yb = np.asarray(y[idx_sorted], dtype=np.float32)
            yield Xb, yb

    ds = tf.data.Dataset.from_generator(
        gen,
        output_signature=(
            tf.TensorSpec(shape=(None, INPUT_WINDOW, NUM_FEATURES), dtype=tf.float32),
            tf.TensorSpec(shape=(None, TARGET_HORIZON, NUM_TARGETS), dtype=tf.float32),
        ),
    )
    ds = ds.prefetch(tf.data.AUTOTUNE)

    steps = int(np.ceil(n / batch_size))
    return ds, n, steps

def build_datasets() -> tuple:
    required = [X_TRAIN_PATH, Y_TRAIN_PATH, X_VAL_PATH, Y_VAL_PATH, X_TEST_PATH, Y_TEST_PATH]
    for p in required:
        if not p.exists():
            raise FileNotFoundError(
                f"Tensor file not found: {p}\nRun 1_prepare_forecast.py before training."
            )

    train_ds, n_train, steps_train = make_dataset(X_TRAIN_PATH, Y_TRAIN_PATH, BATCH_SIZE, shuffle=True)
    val_ds,   n_val,   steps_val   = make_dataset(X_VAL_PATH,   Y_VAL_PATH,   BATCH_SIZE, shuffle=False)
    test_ds,  n_test,  steps_test  = make_dataset(X_TEST_PATH,  Y_TEST_PATH,  BATCH_SIZE, shuffle=False)

    print(f"[LOAD] train rows: {n_train:,}  ({steps_train} steps/epoch)")
    print(f"[LOAD] val   rows: {n_val:,}  ({steps_val} steps)")
    print(f"[LOAD] test  rows: {n_test:,}  ({steps_test} steps)")

    return (train_ds, steps_train), (val_ds, steps_val), (test_ds, steps_test)

def build_gru_forecaster() -> Model:
    inputs = Input(shape=(INPUT_WINDOW, NUM_FEATURES), name="context_window")

    x = GRU(
        units             = GRU_UNITS_1,
        return_sequences  = True,
        recurrent_dropout = RECURRENT_DROPOUT,
        name              = "gru_encoder_1",
    )(inputs)

    x = Dropout(DROPOUT_RATE, name="dropout_1")(x)

    x = GRU(
        units             = GRU_UNITS_2,
        return_sequences  = False,
        recurrent_dropout = RECURRENT_DROPOUT,
        name              = "gru_encoder_2",
    )(x)

    x = Dropout(DROPOUT_RATE, name="dropout_2")(x)

    x = Dense(
        units      = TARGET_HORIZON * NUM_TARGETS,
        activation = "linear",
        name       = "dense_projection",
    )(x)

    x = tf.keras.layers.Activation("linear", dtype="float32", name="cast_to_fp32")(x)

    outputs = Reshape(
        target_shape = (TARGET_HORIZON, NUM_TARGETS),
        name         = "forecast_output",
    )(x)

    model = Model(inputs=inputs, outputs=outputs, name="TripSmart_GRU_Forecaster")
    return model

def build_callbacks() -> list:
    return [
        EarlyStopping(
            monitor              = "val_loss",
            patience             = EARLY_STOP_PATIENCE,
            restore_best_weights = True,
            verbose              = 1,
        ),
        ModelCheckpoint(
            filepath          = str(BEST_CKPT_PATH),
            monitor           = "val_loss",
            save_best_only    = True,
            save_weights_only = False,
            verbose           = 1,
        ),
        ReduceLROnPlateau(
            monitor   = "val_loss",
            factor    = LR_REDUCE_FACTOR,
            patience  = LR_REDUCE_PATIENCE,
            min_lr    = LR_MIN,
            verbose   = 1,
        ),
        TensorBoard(
            log_dir        = str(TB_LOG_DIR),
            histogram_freq = 0,
            write_graph    = False,
        ),
        CSVLogger(
            filename = str(CSV_LOG_PATH),
            append   = False,
        ),
    ]

def train(model: Model, train_ds, steps_train, val_ds, steps_val):
    model.compile(
        optimizer = Adam(learning_rate=LEARNING_RATE, clipnorm=1.0),
        loss      = Huber(delta=HUBER_DELTA, name="huber_loss"),
        metrics   = ["mae", "mse"],
    )

    model.summary(line_length=80)

    history = model.fit(
        train_ds,
        steps_per_epoch  = steps_train,
        validation_data  = val_ds,
        validation_steps = steps_val,
        epochs           = MAX_EPOCHS,
        callbacks         = build_callbacks(),
        verbose          = 1,
    )

    return history

def evaluate(model: Model, test_ds, steps_test: int) -> dict:
    results = model.evaluate(test_ds, steps=steps_test, verbose=1)
    metric_names = model.metrics_names
    metrics = {name: float(val) for name, val in zip(metric_names, results)}

    print("\n[TEST EVALUATION]")
    for name, val in metrics.items():
        print(f"  {name:<20s}: {val:.6f}")

    target_labels = ["Temperature_C", "Precipitation_mm", "Humidity_%"]
    squared_error_sums = np.zeros(NUM_TARGETS, dtype=np.float64)
    total_elements = 0

    for Xb, yb in test_ds.take(steps_test):
        yp = model.predict_on_batch(Xb)
        yb_np = yb.numpy()
        squared_error_sums += np.sum((yp - yb_np) ** 2, axis=(0, 1))
        total_elements += yb_np.shape[0] * yb_np.shape[1]

    rmse_per_target = np.sqrt(squared_error_sums / total_elements)

    print("\n[PER-TARGET RMSE — scaled space]")
    for label, rmse in zip(target_labels, rmse_per_target):
        print(f"  {label:<20s}: {rmse:.6f}")
        metrics[f"rmse_scaled_{label}"] = float(rmse)

    return metrics

def save_artifacts(model: Model, history: tf.keras.callbacks.History, metrics: dict) -> None:
    model.save(MODEL_SAVE_PATH)
    print(f"\n[SAVED] Final model   → {MODEL_SAVE_PATH}")
    print(f"[SAVED] Best checkpoint → {BEST_CKPT_PATH}")

    history_payload = {
        "run_timestamp":  RUN_TIMESTAMP,
        "hyperparameters": {
            "input_window":        INPUT_WINDOW,
            "target_horizon":      TARGET_HORIZON,
            "num_features":        NUM_FEATURES,
            "num_targets":         NUM_TARGETS,
            "gru_units_1":         GRU_UNITS_1,
            "gru_units_2":         GRU_UNITS_2,
            "dropout_rate":        DROPOUT_RATE,
            "recurrent_dropout":   RECURRENT_DROPOUT,
            "learning_rate":       LEARNING_RATE,
            "huber_delta":         HUBER_DELTA,
            "batch_size":          BATCH_SIZE,
            "max_epochs":          MAX_EPOCHS,
            "early_stop_patience": EARLY_STOP_PATIENCE,
            "mixed_precision":     "mixed_float16",
        },
        "training_history": {k: [float(v) for v in vals] for k, vals in history.history.items()},
        "test_metrics": metrics,
    }

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history_payload, f, indent=2)

    print(f"[SAVED] Training history → {HISTORY_PATH}")
    print(f"[SAVED] TensorBoard logs → {TB_LOG_DIR}")
    print(f"[SAVED] CSV training log → {CSV_LOG_PATH}")

def main() -> None:
    print("=" * 70)
    print("  TRIP SMART — ATMOSPHERIC FORECASTING: GRU TRAINING PIPELINE")
    print(f"  Run ID: {RUN_TIMESTAMP}")
    print("=" * 70)

    print("\n[STEP 1] Building tf.data streaming pipelines ...")
    (train_ds, steps_train), (val_ds, steps_val), (test_ds, steps_test) = build_datasets()

    print("\n[STEP 2] Building GRU forecaster architecture (cuDNN-eligible, mixed precision) ...")
    model = build_gru_forecaster()

    print("\n[STEP 3] Starting training pipeline ...")
    history = train(model, train_ds, steps_train, val_ds, steps_val)

    best_epoch = int(np.argmin(history.history["val_loss"])) + 1
    best_val   = float(min(history.history["val_loss"]))
    print(f"\n[TRAINING] Best val_loss: {best_val:.6f} at epoch {best_epoch}")

    print("\n[STEP 4] Evaluating on held-out test set ...")
    metrics = evaluate(model, test_ds, steps_test)

    print("\n[STEP 5] Saving model and artifacts ...")
    save_artifacts(model, history, metrics)

    print("\n[DONE] Training pipeline complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()