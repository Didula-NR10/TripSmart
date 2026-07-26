"""
01_gru_seq2seq/model.py
──────────────────────────
Encoder-decoder GRU — the most direct upgrade over the currently-shipped
model.

What's different from best_checkpoint.keras: the production model is
Encoder(GRU 128 -> GRU 64) -> Dropout -> Dense(72) -> Reshape(24, 3). That
Dense(72) head treats "predict the next 24 hours" as one flat regression
problem — it has no notion that hour 5 comes before hour 6, so it can't use
its own hour-5 prediction to inform hour-6. A proper sequence decoder can:
the encoder compresses the 168h context into a state vector, and a decoder
GRU unrolls 24 steps from that state, each step seeing what step came
before it (via the recurrent state) — the standard seq2seq pattern used for
multi-step time series forecasting.

Still no attention here (that's 03_seq2seq_attention) — this folder isolates
"does a proper decoder alone help" from "does attention on top of a decoder
help further."
"""
from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers, models


def build_model(
    input_window: int,
    n_features: int,
    horizon: int,
    n_targets: int,
    encoder_units: int = 128,
    decoder_units: int = 96,
    dropout: float = 0.2,
) -> tf.keras.Model:
    inputs = layers.Input(shape=(input_window, n_features), name="context_window")

    # Encoder: compress the 168h context into a final state.
    x = layers.GRU(encoder_units, return_sequences=True, name="encoder_gru_1")(inputs)
    x = layers.Dropout(dropout, name="encoder_dropout_1")(x)
    _, encoder_state = layers.GRU(decoder_units, return_state=True, name="encoder_gru_2")(x)

    # Decoder: unroll `horizon` steps from that state. RepeatVector feeds the
    # SAME context vector as input at every decode step (a common, robust
    # seq2seq pattern when there's no separate "known future input" to feed
    # the decoder) — the decoder's own recurrent state is what lets step t
    # depend on step t-1, not the (constant) input.
    context = layers.RepeatVector(horizon, name="repeat_context")(
        layers.GlobalAveragePooling1D(name="encoder_pool")(x)
    )
    decoded = layers.GRU(decoder_units, return_sequences=True, name="decoder_gru")(
        context, initial_state=encoder_state
    )
    decoded = layers.Dropout(dropout, name="decoder_dropout")(decoded)

    outputs = layers.TimeDistributed(layers.Dense(n_targets), name="forecast_output")(decoded)

    model = models.Model(inputs, outputs, name="GRU_Seq2Seq_Forecaster")
    return model
