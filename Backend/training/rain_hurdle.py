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

    occurrence = tf.keras.layers.Dense(horizon, activation="sigmoid", name="rain_occurrence")(summary)
    amount = tf.keras.layers.Dense(horizon, activation="relu", name="rain_amount")(summary)

    hurdle_model = tf.keras.Model(inputs=base_model.input, outputs=[occurrence, amount],
                                   name="TripSmart_Rain_Hurdle")
    return hurdle_model


def compile_hurdle_model(hurdle_model, learning_rate: float):
    import tensorflow as tf

    hurdle_model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss={"rain_occurrence": "binary_crossentropy", "rain_amount": "mse"},
        loss_weights={"rain_occurrence": 1.0, "rain_amount": 1.0},
        metrics={"rain_occurrence": ["accuracy"], "rain_amount": ["mae"]},
    )
    return hurdle_model


def occurrence_and_amount_targets(rain_real_units: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(n, horizon) real-mm rain -> (occurrence 0/1, amount, sample_weight mask
    for the amount head). Anything at or below the project's existing
    zero-floor counts as "didn't rain" — same threshold used everywhere else
    in this repo (forecast/utils.py: RAIN_ZERO_FLOOR_MM), so the hurdle
    model's definition of "rained" matches what the rest of the system
    already treats as a real rain event."""
    from training.config import RAIN_ZERO_FLOOR_MM

    occurred = (rain_real_units > RAIN_ZERO_FLOOR_MM).astype(np.float32)
    return occurred, rain_real_units.astype(np.float32), occurred.copy()


def predict_rain(occurrence_prob: np.ndarray, amount_pred: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """The actual hurdle combination: only trust the amount head's number on
    hours the occurrence head is confident enough it rained at all."""
    return np.where(occurrence_prob >= threshold, np.clip(amount_pred, 0.0, None), 0.0)
