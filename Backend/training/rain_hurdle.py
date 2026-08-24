"""
training.rain_hurdle
──────────────────────
The actual fix for rain, as opposed to just retraining the existing setup
harder. A plain MSE regressor trained on a mostly-zero target (rain) learns
to hedge with a small positive constant instead of committing to 0.0 — that
is a loss-function mismatch, not a data or weight-staleness problem, so more
retraining on the shared temp/humidity/rain output can never fix it.

This builds a HURDLE MODEL instead: two small heads bolted onto the SAME
168h->summary GRU encoder the shipped model already has, but trained
separately from temp/humidity, with a loss suited to zero-inflated data:

  1. `rain_occurrence` — "will it rain this hour?" (binary classification,
     one probability per of the 24 lead hours).
  2. `rain_amount` — "how much, IF it rains?" (regression, trained ONLY on
     hours that actually had rain — see `train.py`'s sample_weight use).

The final rain estimate for hour h is occurrence_prob[h] >= threshold ?
amount_pred[h] : 0.0 — see `predict_rain`.

Why the shared encoder is FROZEN here, not fine-tuned: `build_hurdle_model`
takes the already-deployed model and taps its 64-dim summary layer by
reference — in Keras, layers are shared objects, not copies, so training an
unfrozen encoder through this model would also silently change the
production temp/humidity model's weights (they use the literal same layer
instances). Freezing treats "168h of weather -> a summary vector" as an
already-proven representation (it is — that's what the shipped temp/humidity
backtests demonstrate) and trains only the new rain-specific heads on top of
it, which also means this can never regress temp/humidity by construction.
"""
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
    """Returns a NEW two-output Keras model: [rain_occurrence, rain_amount],
    sharing (and freezing) the base model's encoder. The base model itself is
    left completely untouched — its own weights are never modified."""
    import tensorflow as tf

    summary = _find_encoder_output(base_model)  # (None, 64)

    for layer in base_model.layers:
        layer.trainable = False
    log.info("Encoder frozen (%d layers) — only the two new rain heads will train.",
              len(base_model.layers))

    # A small shared hidden layer gives the two new heads a bit of nonlinear
    # capacity of their own, rather than each being one flat Dense straight
    # off the frozen 64-dim summary — modest (32 units) on purpose, since the
    # amount of real rain-labeled data available is still small.
    rain_hidden = tf.keras.layers.Dense(32, activation="relu", name="rain_hidden")(summary)
    occurrence = tf.keras.layers.Dense(horizon, activation="sigmoid", name="rain_occurrence")(rain_hidden)
    amount = tf.keras.layers.Dense(horizon, activation="relu", name="rain_amount")(rain_hidden)

    # Outputs as a DICT, not a list: Keras 3's trainer resolves dict-keyed
    # losses/sample_weight against the model's output structure directly, and
    # a list-output model doesn't structurally match a dict loss spec the way
    # Keras 2 used to allow (hit this as a real KeyError during a live run).
    hurdle_model = tf.keras.Model(
        inputs=base_model.input,
        outputs={"rain_occurrence": occurrence, "rain_amount": amount},
        name="TripSmart_Rain_Hurdle",
    )
    return hurdle_model


def build_standalone_rain_model(input_window: int, n_features: int, horizon: int = 24,
                                 gru1_units: int = 64, gru2_units: int = 32):
    """A FRESH, from-scratch GRU sized for the extended feature set (see
    extended_features.py) — not a reuse of the shipped temp/humidity model's
    encoder, because that encoder's Input shape (168, 12) is fixed and can't
    accept the wider (168, 22) extended feature vector. Deliberately smaller
    (64->32 vs the shipped model's 128->64) since this is a standalone,
    rain-only model and the point-of-diminishing-returns for model size is
    lower on a single-channel target than the shipped 3-channel one."""
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
    """Custom loss for the amount head: y_true is (batch, 2*horizon) — the
    real amount concatenated with the occurrence mask (see
    occurrence_and_amount_targets). Keras's built-in `sample_weight` reduces
    a multi-step loss to one scalar per SAMPLE before weighting, which can't
    express "mask out individual lead-hours within one sample" — hit this as
    a real shape-mismatch error during training, hence doing the masking
    inside the loss itself instead."""
    import tensorflow as tf

    horizon = y_pred.shape[-1]
    amount, mask = y_true[:, :horizon], y_true[:, horizon:]
    sq_err = tf.square(amount - y_pred) * mask
    denom = tf.reduce_sum(mask, axis=-1) + 1e-6  # avoid /0 on a sample with zero rain hours
    return tf.reduce_sum(sq_err, axis=-1) / denom


def weighted_occurrence_bce(pos_weight: float):
    """Binary cross-entropy that costs `pos_weight` times more to miss a real
    rain hour than to wrongly call a dry one. Plain BCE on rain (rare) vs
    no-rain (common) trains a classifier to minimize total error by just
    always predicting "no rain" — confirmed as the actual failure mode in a
    live run here (recall 0.007: 44 real rain hours caught out of 6,452).
    `pos_weight` should be roughly (count of dry hours / count of rain hours)
    in the training set — see occurrence_pos_weight()."""
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
    """How many times rarer "rained" is than "didn't rain" in this training
    set. The full inverse-frequency ratio (damping=1.0) is the textbook
    starting point, but empirically over-corrected here — a live run at the
    full 8.76x weight pushed recall from 0.7% to 64% but collapsed precision
    to 19% and made overall MAE/R² worse than the unweighted baseline.
    `damping` < 1.0 moderates the weight (e.g. 0.35 -> roughly a third of the
    full ratio) without abandoning class-weighting altogether."""
    n_positive = float(np.sum(occurrence_labels))
    n_negative = float(occurrence_labels.size - n_positive)
    full_weight = max(n_negative / n_positive, 1.0) if n_positive > 0 else 1.0
    return max(1.0, 1.0 + (full_weight - 1.0) * damping)


def best_threshold_by_f1(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Scans candidate thresholds and returns the one maximizing F1 — a fixed
    0.5 cutoff is meaningless once the classes are this imbalanced (a
    well-calibrated model can legitimately never output > 0.5 for the rare
    class even while ranking rain hours correctly above dry ones). ALWAYS
    call this on validation data, never on the holdout you report against,
    or the reported score is no longer honestly out-of-sample."""
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
    """(n, horizon) real-mm rain -> (occurrence 0/1, amount_target). The
    second return value is (n, 2*horizon): the real amount concatenated with
    its own occurrence mask, which masked_amount_mse splits back apart — see
    that function's docstring for why the mask rides along in the target
    instead of going through sample_weight. Anything at or below the
    project's existing zero-floor counts as "didn't rain" — same threshold
    used everywhere else in this repo (forecast/utils.py:
    RAIN_ZERO_FLOOR_MM), so the hurdle model's definition of "rained"
    matches what the rest of the system already treats as a real rain
    event."""
    from training.config import RAIN_ZERO_FLOOR_MM

    occurred = (rain_real_units > RAIN_ZERO_FLOOR_MM).astype(np.float32)
    amount = rain_real_units.astype(np.float32)
    amount_target = np.concatenate([amount, occurred], axis=-1)
    return occurred, amount_target


def predict_rain(occurrence_prob: np.ndarray, amount_pred: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """The actual hurdle combination: only trust the amount head's number on
    hours the occurrence head is confident enough it rained at all."""
    return np.where(occurrence_prob >= threshold, np.clip(amount_pred, 0.0, None), 0.0)
