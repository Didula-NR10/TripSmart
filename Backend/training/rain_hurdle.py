from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger("trip_smart.training.rain_hurdle")

ENCODER_OUTPUT_LAYER_CANDIDATES = ("dropout_2", "gru_encoder_2")

def _find_encoder_output(base_model):
    for name in ENCODER_OUTPUT_LAYER_CANDIDATES:
        try:
            return base_model.get_layer(name).output
        except ValueError:
            continue
    raise ValueError(
        f"Could not find the shared encoder's summary layer on the base model "
        f"(tried {ENCODER_OUTPUT_LAYER_CANDIDATES}) — the shipped architecture "
        f"must have changed; update ENCODER_OUTPUT_LAYER_CANDIDATES."
    )

def build_hurdle_model(base_model, horizon: int = 24):
    import tensorflow as tf

    summary = _find_encoder_output(base_model)

    for layer in base_model.layers:
        layer.trainable = False
    log.info("Encoder frozen (%d layers) — only the two new rain heads will train.",
              len(base_model.layers))

    rain_hidden = tf.keras.layers.Dense(32, activation="relu", name="rain_hidden")(summary)
    occurrence = tf.keras.layers.Dense(horizon, activation="sigmoid", name="rain_occurrence")(rain_hidden)
    amount = tf.keras.layers.Dense(horizon, activation="relu", name="rain_amount")(rain_hidden)

    hurdle_model = tf.keras.Model(
        inputs=base_model.input,
        outputs={"rain_occurrence": occurrence, "rain_amount": amount},
        name="TripSmart_Rain_Hurdle",
    )
    return hurdle_model

def build_standalone_rain_model(input_window: int, n_features: int, horizon: int = 24,
                                 gru1_units: int = 64, gru2_units: int = 32):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(input_window, n_features), name="context_window")
    x = tf.keras.layers.GRU(gru1_units, return_sequences=True, name="rain_gru_1")(inputs)
    x = tf.keras.layers.Dropout(0.2, name="rain_dropout_1")(x)
    x = tf.keras.layers.GRU(gru2_units, name="rain_gru_2")(x)
    x = tf.keras.layers.Dropout(0.2, name="rain_dropout_2")(x)
    hidden = tf.keras.layers.Dense(32, activation="relu", name="rain_hidden")(x)
    occurrence = tf.keras.layers.Dense(horizon, activation="sigmoid", name="rain_occurrence")(hidden)
    amount = tf.keras.layers.Dense(horizon, activation="relu", name="rain_amount")(hidden)

    return tf.keras.Model(
        inputs=inputs,
        outputs={"rain_occurrence": occurrence, "rain_amount": amount},
        name="TripSmart_Rain_Extended",
    )

def masked_amount_mse(y_true, y_pred):
    import tensorflow as tf

    horizon = y_pred.shape[-1]
    amount, mask = y_true[:, :horizon], y_true[:, horizon:]
    sq_err = tf.square(amount - y_pred) * mask
    denom = tf.reduce_sum(mask, axis=-1) + 1e-6
    return tf.reduce_sum(sq_err, axis=-1) / denom

def weighted_occurrence_bce(pos_weight: float):
    import tensorflow as tf

    def loss(y_true, y_pred):
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)
        per_element = -(
            pos_weight * y_true * tf.math.log(y_pred)
            + (1 - y_true) * tf.math.log(1 - y_pred)
        )
        return tf.reduce_mean(per_element, axis=-1)

    return loss

def occurrence_pos_weight(occurrence_labels: np.ndarray, damping: float = 1.0) -> float:
    n_positive = float(np.sum(occurrence_labels))
    n_negative = float(occurrence_labels.size - n_positive)
    full_weight = max(n_negative / n_positive, 1.0) if n_positive > 0 else 1.0
    return max(1.0, 1.0 + (full_weight - 1.0) * damping)

def best_threshold_by_f1(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    y_true_flat, y_prob_flat = y_true.ravel(), y_prob.ravel()
    best_t, best_f1 = 0.5, -1.0
    for t in np.linspace(0.01, 0.99, 99):
        pred = (y_prob_flat >= t).astype(int)
        tp = np.sum((pred == 1) & (y_true_flat == 1))
        fp = np.sum((pred == 1) & (y_true_flat == 0))
        fn = np.sum((pred == 0) & (y_true_flat == 1))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return best_t

def compile_hurdle_model(hurdle_model, learning_rate: float, pos_weight: float = 1.0):
    import tensorflow as tf

    hurdle_model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss={
            "rain_occurrence": weighted_occurrence_bce(pos_weight),
            "rain_amount": masked_amount_mse,
        },
        loss_weights={"rain_occurrence": 1.0, "rain_amount": 1.0},
    )
    return hurdle_model

def occurrence_and_amount_targets(rain_real_units: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from training.config import RAIN_ZERO_FLOOR_MM

    occurred = (rain_real_units > RAIN_ZERO_FLOOR_MM).astype(np.float32)
    amount = rain_real_units.astype(np.float32)
    amount_target = np.concatenate([amount, occurred], axis=-1)
    return occurred, amount_target

def predict_rain(occurrence_prob: np.ndarray, amount_pred: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    return np.where(occurrence_prob >= threshold, np.clip(amount_pred, 0.0, None), 0.0)
